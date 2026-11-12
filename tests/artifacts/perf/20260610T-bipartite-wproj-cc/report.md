# perf(bipartite weighted projections): de-delegate, in-process

br-r37-c1-0y2fn

## Problem
The four weighted bipartite projections were slow vs nx (2.1–3.96×):
- `weighted_projected_graph` / `overlap_weighted_projected_graph` /
  `generic_weighted_projected_graph` **delegated** to nx + `_from_nx_graph`
  (the double-conversion tax, like `projected_graph`);
- `collaboration_weighted_projected_graph` was already a Python port but read
  adjacency through per-access `B[u]` / `B[nbr]` / `pred[v]` AtlasViews (3.96×,
  the worst).

## Lever (one)
One shared scaffold `_weighted_projection_inprocess(B, nodes, weight_fn)` for the
simple undirected fnx-`Graph` case: snapshot `B`'s adjacency ONCE via the native
key-only binding (`_native_adjacency_keys`) into Python sets, then for each `u`
join it to every second-neighbour `v`, computing the edge weight via `weight_fn`:
- weighted: `len(un & vn)` (or `/n_top` if ratio; n_top<1 keeps the nx-raising
  delegation path);
- overlap: `len(un & vn) / len(un | vn)` (jaccard) or `/min(len(un),len(vn))`;
- generic (default fn only): `len(un & vn)`;
- collaboration: `sum(1/(len(adj[k])-1) for k in un & vn if len(adj[k])>1)`.
Directed / multigraph / nx-typed `B` (and a custom `generic` weight_function)
keep the delegation/port path. Set ops and `len(adj[k])` degrees are exactly
nx's computations, so weights are bit-identical.

Touched: `python/franken_networkx/bipartite.py`. Python-only.

## Proof (nx-exact)
`harness_proof.py`: 54 calls — all 6 variant forms × 9 graphs (bipartite gnp ×8
seeds + a string-labelled degree-mixed case). Nodes+attrs and edges with
`weight` (floats rounded to 12 dp) **== nx, 0 mismatches**.
Golden sha256 (== nx):
`43efa026af52a6d856be0f6d2fb33d1f17717adb807861251b0879b93cbb41ca`
pytest -k "projected/bipartite/collaboration/overlap": **470 passed**.

## Timing (warm interleaved min-of-5, backend disabled, random_graph(200,160,0.04))
| variant | baseline fnx | nx | base ratio | new fnx | new ratio | self-speedup |
|---------|-------------:|---:|-----------:|--------:|----------:|-------------:|
| weighted | 35.30 ms | 13.67 ms | 2.66× | 15.22 ms | 1.11× | 2.3× |
| overlap | 37.51 ms | 17.50 ms | 2.13× | 16.86 ms | 0.96× | 2.2× |
| generic | 37.88 ms | 16.83 ms | 2.28× | 12.36 ms | **0.73×** | 3.1× |
| collab | 79.96 ms | 19.64 ms | 3.96× | 15.24 ms | **0.78×** | 5.2× |

2.1–3.96× slower → 0.73–1.11× (parity-to-faster), 2.2–5.2× self-speedup.

## Score
Impact: high (2.2–5.2× self-speedup → parity-to-faster across four bipartite
projection variants; collaboration 3.96×→0.78×). Confidence: high
(byte-identical golden sha incl. float weights, 0/54, 470 tests). Effort: low
(one shared in-process scaffold, Python-only). Score >> 2.0.
