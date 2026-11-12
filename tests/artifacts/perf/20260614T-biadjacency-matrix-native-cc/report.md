# bipartite.biadjacency_matrix de-dispatch — 4.15x slower → ~1.2x (3.4x self-speedup), byte-exact

Bead: br-r37-c1-r2h3w
Agent: cc / 2026-06-14

## Problem

`fnx.bipartite.biadjacency_matrix` was re-exported straight from
`networkx.algorithms.bipartite` (`from ...bipartite import *`), so it ran nx's
`@nx._dispatchable` version — which round-trips the WHOLE fnx graph through
`_fnx_to_nx` (full O(V+E) conversion) before building the sparse matrix. ~4.15x
slower than nx on a native graph (1.03ms vs 0.25ms at 80×60/400 edges).

## Fix (concrete bipartite.py override, COO built directly from fnx)

Added a concrete `biadjacency_matrix` to `bipartite.py` that reproduces nx's
exact algorithm but sources edges directly from the fnx graph
(`B.edges(row_order, data=True)`) — no conversion. Byte-identical because:

- `coo_array(...).asformat(...)` canonicalises, so the (row, col, data) triple
  SET fully determines the matrix — edge iteration order is irrelevant.
- Default `column_order = list(set(B) - set(row_order))` reproduces nx's
  arbitrary-but-deterministic CPython set order exactly (identical node values →
  identical set → identical list order).
- Directed graphs iterate successors only (== nx's `B.edges(row_order)`).
- Validation (`row_order is empty list`, duplicate row/column ordering,
  `Unknown sparse array format: …`) and `weight=None` (all-ones) match nx exactly.

## Proof

- 600-case parity sweep: 25 seeds × {weighted, unweighted} × {csr, csc, coo,
  dense, lil, dok} × {default column_order, explicit column_order}, comparing
  dense forms vs nx — **0 mismatches**.
- `weight=None` all-ones matrix matches nx; error parity (empty row_order,
  bad format) identical class+message.
- Golden (gnmk 30×25/150 weighted): dense sha256 `2c0337ce2b6db638…`, equals nx.
- Targeted (`-k 'bipartite or biadjacency or matrix'`): 2231 passed (1 known
  pre-existing coverage-matrix-doc failure). Full suite: only known pre-existing.

## Timing (interleaved min-of-200)

| size (top×bottom/edges) | before (dispatched) | after (fnx) | nx | now vs nx |
|-------------------------|---------------------|-------------|-----|-----------|
| 80×60 / 400   | ~1.03ms | 0.280ms | 0.246ms | 1.14x |
| 200×150 / 1500 | — | 0.865ms | 0.675ms | 1.28x |
| 400×300 / 4000 | — | 2.25ms | 1.87ms | 1.20x |

4.15x slower → ~1.2x: a 3.4x self-speedup that removes the O(V+E) conversion
tax. The residual ~1.2x is the fnx edges-view PyO3 iteration floor vs nx's C
adjacency. Pure-Python.

## Residual / next lever

Closing the last ~1.2x to <1.0x needs a native rectangular-COO kernel (emit
(row_idx, col_idx, weight) over the row-node adjacency in Rust, given the row/col
index maps) wrapped into scipy — analogous to the existing native `to_scipy_array`
COO path but for an arbitrary node-subset × node-subset submatrix. Filed as
follow-up.
