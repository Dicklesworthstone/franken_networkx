# Multigraph matrix exporters — route default weighted call through native COO

Bead: br-r37-c1-iyu0a (partial)
Agent: cc (CopperCliff)
Date: 2026-06-20

## Problem

`to_numpy_array` / `to_scipy_sparse_array` on MultiGraph/MultiDiGraph fell to a
Python `G.edges(keys=True, data=True)` parallel-edge dict-of-lists loop for the
**default** `weight='weight', dtype=None` call. A native COO kernel
(`adjacency_arrays_multigraph`) already existed but was gated out:

- `to_scipy_sparse_array`: gate required `dtype is not None` (to dodge nx's
  int/float inference), so the default `dtype=None` call skipped it.
- `to_numpy_array`: had no native multigraph path at all.

Baseline (n=500, p=0.02): to_numpy MG 0.42x, to_scipy MG 0.39x, to_numpy MDG
0.56x, to_scipy MDG 0.41x — all clear losses.

## Fix (pure-Python: route to the already-built native kernel)

- `to_scipy_sparse_array`: admit `weight=str, dtype=None` to the native path.
  The body already reproduces nx's int/float inference
  (`array_equal(data, data.astype(int64))`). Because the f64 helper silently
  coerces non-numeric/non-finite weights to the default, guard with the native
  `graph_has_nonfinite_edge_weight_multigraph` scan (use native only when every
  present weight is finite-numeric; absent => default 1, matching nx).
- `to_numpy_array`: add a native multigraph path for the default
  `multigraph_weight=sum`, `nonedge=0` case — `np.add.at` accumulates the
  per-parallel-edge COO entries (= sum of parallel weights). Same non-finite
  guard.

## Proof

- `bench_and_parity.py`: **160 configs × 2 exporters = 320 checks, 0 fails** —
  int/float/missing weights, self-loops, MultiGraph + MultiDiGraph, value AND
  dtype AND sparsity-pattern. Golden sha256
  `bff9639b02900c23d43c585672cddf6a3e39676fa40c631efccec93bfeb44307`.
- Conformance: 586 passed in the to_numpy/to_scipy/adjacency_matrix/sparse family.

## Timing (interleaved min-of-15; baseline → after)

| exporter            | baseline | after  | nx      |
|---------------------|----------|--------|---------|
| to_numpy MultiGraph | 0.42x    | **1.00x** | 2.4ms |
| to_scipy MultiGraph | 0.39x    | **0.86x** | 2.2ms |
| to_numpy MultiDiGraph | 0.56x  | **0.69x** | 5.2ms |
| to_scipy MultiDiGraph | 0.41x  | **0.58x** | 3.4ms |

Strict improvement on all four (loss → near-parity/win); none regress. `adjacency_matrix`
(calls `to_scipy`) inherits the MG win.

## Residual (Rust-crate, filed under iyu0a)

The remaining MultiDiGraph gap is two native-side costs the pure-Python reroute
can't remove: (1) `_sync_rust_edge_attrs` is ~2.5ms for MultiDiGraph (a no-op
for MultiGraph — MDG lacks the dirty-flag fast path); (2)
`adjacency_arrays_multigraph` stringifies every nodelist node
(`node_key_to_string`) instead of using an integer-index path like the
simple-graph `adjacency_index_arrays`. Closing those needs Rust work in
fnx-python.
