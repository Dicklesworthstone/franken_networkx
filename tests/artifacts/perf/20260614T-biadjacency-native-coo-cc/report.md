# Native biadjacency rectangular-COO kernel — 1.28x slower → 0.63-0.71x (beats nx)

Bead: br-r37-c1-18cp7
Agent: cc / 2026-06-14

## Problem

`fnx.bipartite.biadjacency_matrix` was de-dispatched to pure Python in 79e8c8133
(4.15x→~1.2x by removing the fnx→nx conversion), but the residual ~1.28x vs nx
was the per-edge `B.edges(row_order, data=True)` PyO3 iteration floor.

## Fix (native rectangular-COO kernel)

Added `_fnx.biadjacency_coo(B, row_order, column_order, weight)` in
crates/fnx-python/src/algorithms.rs: builds the `(rows, cols, data)` COO triple
over the integer-CSR adjacency (`edges_ordered_borrowed`) in one Rust pass, each
undirected edge visited once and emitted from whichever endpoint lands in
`row_order` (the other in `column_order`) — matching nx's `u in row_index and
v in col_index` filter. Returns a 4th value `all_int` (true iff every emitted
weight is an integer or the missing-attr default 1).

**dtype parity (the one subtlety):** nx builds the COO from `d.get(weight, 1)`
Python values, so numpy infers `int64` for an all-integer matrix and `float64`
otherwise. The kernel's `all_int` flag lets the Python wrapper reproduce this
exactly: `int64` for a non-empty all-integer matrix, else `float64` (empty →
`float64`, matching numpy's empty-list inference). Order is irrelevant —
`coo_array(...).asformat(...)` canonicalises, so the triple SET determines the
matrix. Directed / multigraph / nx-typed / non-numeric-weight inputs return
`None` → exact Python loop fallback.

## Proof

- 320-case parity sweep: 40 seeds × {unweighted, int-weight, float-weight} ×
  {csr, csc, coo, dense} × {default, explicit column_order}, comparing dense
  forms **AND dtype** vs nx — 0 mismatches.
- dtype checks: int-weight → `int64==int64`; `weight=None` → `int64==int64`;
  float-weight → `float64`.
- Golden (gnmk 30×25/150): dense sha256 `d5b052cd2f42e554…`, equals nx.
- Targeted bipartite/matrix + full suite (remote, kernel confirmed): only the 6
  known pre-existing failures.

## Timing (min-of-20)

| size (top×bottom/edges) | before (pure-Python) | after (native COO) | nx | now vs nx |
|-------------------------|----------------------|--------------------|-----|-----------|
| 200×150 / 1500 | ~0.90ms (1.28x) | 0.469ms | 0.672ms | **0.71x** |
| 400×300 / 4000 | — | 1.174ms | 1.865ms | **0.63x** |

The native COO eliminates the per-edge PyO3 floor; biadjacency_matrix now beats
nx. Completes the bipartite-matrix family (gap closed end-to-end: 4.15x → 0.63x).
