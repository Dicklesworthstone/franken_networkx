# DiGraph `_native_edges_no_data` — index-based node-key iteration: 12.19ms → 6.92ms (1.76x self), gap to nx 5.43x → 3.25x

Bead: br-r37-c1-2a00r (substrate lever, part 5 of N)
Agent: cc / 2026-06-14

## Problem

`list(DiGraph.edges())` was 5.43x slower than nx. After the generator rewrite
(e2945afdf) the residual was the kernel `_native_edges_no_data` (digraph.rs): it
walked `inner.edges_ordered_borrowed()` (&str) and called `py_node_key(u)` +
`py_succ_key(u, v)` per edge — a `HashMap<String,PyObject>` canonical-String
hash per endpoint.

## Fix (one lever: same index path as undirected, DiGraph already had the API)

When `succ_py_keys` is empty (uniform successor display objects), build the
`nodes_seq`-cached per-index node-key Vec once (`cached_node_key_vec`) and walk
`edges_ordered_indices()` — which yields `(u, v)` in the SAME node-major
successor order as `edges_ordered_borrowed` (both iterate
`succ_indices.enumerate()` with the identical `edges.contains((u,t))` filter) —
cloning `keys[u]`/`keys[v]` directly (O(1) incref, no String hash). Non-empty
`succ_py_keys` (z6uka) falls through to the exact per-edge `py_succ_key` path.

## Proof (deterministic)

- 60-seed DiGraph parity sweep (int/str/float/mixed node keys) + self-loops:
  **0 mismatches** vs nx.
- Golden `list(DiGraph.edges())` (gnp 400,0.02,seed=7,directed): sha256
  `39462eb4ca55ec7b…` == nx.
- Suite: 7322 passed, only the 1 known pre-existing gexf fail.

## Timing (interleaved min-of-10, warm, n=2000 directed ~40k edges)

| op | before | after | nx | self | vs nx |
|----|--------|-------|-----|------|-------|
| DiGraph edges() | 12.19ms | 6.92ms | 2.13ms | **1.76x** | 5.43x → **3.25x** |

## Residual (2a00r)

The remaining 3.25x is the `_FailFastEdgeIterator` generator guard: 2 PyO3
getattrs per element (`nodes_seq` + `edges_seq`) for 40k edges. A combined
single-FFI guard token (one Rust property returning a packed revision) would
roughly halve the drain — the next sub-lever. (nx's edges() also has no per-edge
attr work for NoData, so this guard FFI is the structural gap.)
