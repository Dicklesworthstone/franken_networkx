# Directed weighted degree_assortativity — vectorized path → 231x faster than nx

Bead: br-r37-c1-degxywt (directed leg)
Agent: cc
Date: 2026-06-14

## Problem

`degree_assortativity_coefficient(DiGraph, weight='weight')` delegated to nx
(the native directed kernel has no weighted path). Both fnx and nx took ~180ms
at 500 nodes / 2000 edges — nx's directed-weighted assortativity is
pathologically slow because its `degree_mixing_matrix` is indexed by distinct
FLOAT weighted-degree values (a near-dense matrix over hundreds of unique
floats). fnx delegated → ~180ms.

## Fix (ONE lever, completes the assortativity family)

`degree_assortativity_coefficient` directed branch: for a simple DiGraph with
`weight is not None`, `x=="out"`, `y=="in"`, `nodes is None`, route to the
vectorized `degree_pearson_correlation_coefficient(G, x, y, weight=weight)`. nx's
directed degree assortativity equals the (out, in) degree-degree Pearson r over
the weighted degree pairs (verified), and `degree_pearson`'s
`_degree_xy_pairs_fast` already grew a weight-aware fast path (e1edcfeb1). The
native unweighted directed kernel stays the fast path; degenerate inputs (fewer
than two degree pairs) make scipy's `pearsonr` raise where nx returns nan, so
those fall through to the nx delegation for exact parity.

## Proof

- 50-seed DiGraph × {weight=None, 'weight'} parity sweep, with some edges missing
  the weight attr (default 1) and empty/degenerate graphs, comparing value AND
  exception type vs nx — **0 mismatches over 100 checks** (rel_tol 1e-7).
- Golden sha256 of all results:
  `5ea98fe3df0dfc453d1b0fd01b7eb318a0ca6352c2cdd2271e68a00634d90c43`.
- Full python suite: only the known pre-existing failures remain.

## Timing (500 nodes / 2000 weighted edges, min-of-5×2)

| op (DiGraph, weight='weight')          | before | after  | nx       | after vs nx | self-speedup |
|----------------------------------------|--------|--------|----------|-------------|--------------|
| degree_assortativity_coefficient       | 180ms  | 0.71ms | 163ms    | 0.004x | ~255x |

The whole degree-assortativity / degree-pearson family (undirected & directed ×
unweighted & weighted × with/without self-loops) is now vectorized and at-or-far-
better than nx. Pure-Python change, no rebuild.

## Note

The shared `__init__.py` + `lib.rs` carry a peer agent's (BoldFalcon) uncommitted
WIP (non-neighbors node-set cache, reverse_view, _multi_add_edges_from,
_try_add_str_keyed_edges_from_batch). This commit was made via a private
GIT_INDEX_FILE applying ONLY the degree_assortativity directed-weighted hunk, so
the peer's work was left untouched.
