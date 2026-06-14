# Weighted degree_assortativity / degree_pearson — vectorized weighted path → beats nx 7-55x

Bead: br-r37-c1-degxywt
Agent: cc
Date: 2026-06-13

## Problem

After the self-loop fix (b440efd0e), the WEIGHTED degree-assortativity /
degree-pearson paths still delegated/walked slow code:

| op (500 nodes / 2000 weighted edges) | before vs nx |
|--------------------------------------|--------------|
| degree_assortativity_coefficient(weight='weight') | 1.22x slower (44ms) |
| degree_pearson_correlation_coefficient(weight='weight') | slow node_degree_xy walk |

`_degree_xy_pairs_fast` (the vectorized scipy-COO degree-pair extractor backing
degree_pearson) bailed on `weight is not None`, and
`degree_assortativity_coefficient` only took its fast undirected branch for
`weight is None`, delegating weighted graphs to nx.

## Fix (ONE lever: weight-aware vectorized degree pairs)

- `_degree_xy_pairs_fast`: drop the `weight is not None` bail and pass `weight`
  through to `to_scipy_sparse_array(weight=weight)`. The weighted COO carries each
  edge's weight (default 1 for a missing attr, matching nx's `degree(weight=...)`
  accumulation), so `A.sum` gives the WEIGHTED degree; the self-loop diagonal
  correction (undirected loop counts ×2) and directed out/in sums all work
  unchanged. Pairs stay one-per-adjacency-entry = node_degree_xy's multiset.
- `degree_pearson` benefits automatically (weighted, undirected AND directed).
- `degree_assortativity_coefficient` undirected branch: take the fast path for
  ANY weight (route to the vectorized `degree_pearson(G, weight=weight)`; nx's
  degree assortativity equals the degree-degree Pearson r over weighted degree
  pairs — verified to ~1e-15). The native unweighted-no-self-loop kernel stays
  the fastest path; degenerate (<2 pairs) cases delegate to nx for nan parity.

## Proof

- 40-seed × {Graph, DiGraph} × {weight=None, 'weight'} parity sweep, with some
  edges missing the weight attr (default 1) and empty/degenerate graphs,
  comparing value AND exception type vs nx — **0 mismatches over 320 checks**
  (rel_tol 1e-7; observed worst abs diff ~1.8e-15).
- Golden sha256 of all results:
  `2c93ab0ef29b3b211b986822c35a0631c9c47bf46409cf17475f0837e7acbfc9`.
- Targeted suite (assortativ/pearson/degree_mixing/node_degree_xy/degenerate):
  811 passed. Full python suite: only the known pre-existing failures remain.

## Timing (500 nodes / 2000 weighted edges, min-of-6×2)

| op (weight='weight')                    | before | after  | nx      | after vs nx | self-speedup |
|-----------------------------------------|--------|--------|---------|-------------|--------------|
| degree_assortativity_coefficient        | 44ms   | 0.90ms | 49.5ms  | 0.02x | ~49x |
| degree_pearson_correlation_coefficient  | ~7ms   | 0.90ms | 7.0ms   | 0.13x | ~7.7x |

nx's weighted `degree_assortativity_coefficient` is pathologically slow (~49ms)
because its degree_mixing_matrix is indexed by distinct FLOAT weighted-degree
values; routing to Pearson r avoids that entirely. Pure-Python change, no rebuild.

## Note

The shared `crates/fnx-python/src/lib.rs` carries a peer agent's uncommitted WIP
(`_try_add_str_keyed_edges_from_batch`, br-r37-c1-04z53.80) — left untouched;
this commit stages only `__init__.py` + this report.
