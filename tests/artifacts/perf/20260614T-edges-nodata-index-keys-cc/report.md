# EdgeView NoData (`G.edges()`) — index-based node-key iteration: 6.76ms → 3.88ms (1.74x self), gap to nx 2.36x → 1.58x

Bead: br-r37-c1-2a00r (substrate lever, part 1 of N)
Agent: cc / 2026-06-14

## Problem (profile-backed)

`list(G.edges())` on a simple Graph was ~2.36x slower than nx (6.76ms vs
2.86ms at n=2000, ~20k edges). `EdgeView.__iter__`'s NoData arm iterated
`inner.edges_ordered_borrowed()` (yielding `&str` endpoints) and called
`py_node_key(left)` + `py_adj_key(left, right)` per edge. `py_node_key`
(lib.rs) does a `HashMap<String, PyObject>.get(canonical)` — **hashing the
canonical String per endpoint, per edge**. nx pays ~0: its adjacency dict keys
are already Python objects, so iteration yields existing references.

## Fix (one lever: iterate by node INDEX, look up the cached key object)

- Added `Graph::edges_ordered_indices()` (crates/fnx-classes/src/lib.rs) — the
  index-space twin of `edges_ordered_borrowed`, yielding `(u, v)` node indices
  in the SAME node-major traversed order/orientation (mirrors the existing
  `adj_indices` walk + `(min,max)` dedup + degenerate-case fallback exactly, so
  output order is byte-identical).
- `EdgeView.__iter__` NoData fast path (crates/fnx-python/src/views.rs): build
  the `nodes_seq`-cached `Vec<PyObject>` of per-index node-key objects once
  (`cached_node_key_vec`, already cached by revision), then for each `(u, v)`
  clone_ref `keys[u]` / `keys[v]` directly — O(1) incref, **no String hash, no
  alloc**.
- **Correctness gate:** only taken when `adj_py_keys.is_empty()`. When it is
  non-empty (non-uniform adjacency-row key objects, br-r37-c1-z6uka) a
  neighbor's display object can differ from the node's own key object, so the
  code falls through to the exact per-edge `py_adj_key` path.

## Proof (parity is deterministic — load-independent)

- NoData key-type sweep: 80 seeds × {int, str, float, mixed} node keys —
  **0 mismatches** vs nx (repr-exact). Plus self-loops, isolated nodes, empty,
  single-edge, cache-reuse consistency — all OK.
- Mutation-during-iteration still raises `RuntimeError` (guard intact).
- data=True / data=attr paths (unchanged code) re-verified: 60-seed sweep +
  live-dict identity + golden — 0 mismatches.
- Golden `list(G.edges())` (gnp 400, 0.025, seed=7): sha256
  `2fc3fbeb0574b09b…`, equals nx.

## Timing (interleaved min-of-10, warm)

| op | before | after | nx | self | vs nx |
|----|--------|-------|-----|------|-------|
| edges() n=2000 (~20k E) | 6.76ms | 3.88ms | 2.46ms | **1.74x** | 2.36x → **1.58x** |
| edges() n=3000 | — | 3.75ms | 2.95ms | — | **1.27x** |

## Residual (filed under 2a00r for follow-up)

The remaining gap to nx is `NodeViewIterator.__next__`: it borrows the graph +
compares `nodes_seq` per element (PyO3 method dispatch per edge) to honor nx's
"changed size during iteration" contract. nx's pure-Python generator has no
per-element FFI. Closing it (without losing the mutation guard) is a separate
lever. The data-bearing paths (`edges(data=True)` 1.66x, `edges(data=attr)`
1.3x) still pay the String-hash + `edge_key` String-alloc tax — next step is
extending the index path to them with index-keyed attr access.
