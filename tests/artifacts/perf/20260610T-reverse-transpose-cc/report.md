# perf(DiGraph.reverse): integer transpose

br-r37-c1-ah6yc

## Problem
`DiGraph.reverse()` (native, in `PyDiGraph::reverse`) rebuilt the reversed
graph the slow way:
1. `self.inner.edges_ordered()` — a full O(E) **deep clone** of every edge's
   endpoints (two `String`s) + `AttrMap` into an `EdgeSnapshot` Vec.
2. A per-edge loop re-cloning each into a `(String, String, AttrMap)` batch.
3. `extend_edges_with_attrs_unrecorded` — which re-hashes each endpoint through
   the `String` name table (`nodes.get_index_of` ~3×/edge) to find integer
   indices it already had.

Pure bulk construction is at parity with nx (`DiGraph(edgelist)` 1.01×), so the
gap was entirely this redundant String/hash churn: reverse was **1.8–1.9×
slower than nx** at 100k–300k edges (e.g. n=1500 gnp directed: 257 ms vs nx
145 ms).

## Lever (one)
**Reverse is a pure transpose.** The reversed graph keeps the *same node table*
(identical insertion order ⇒ identical indices), so:
- reversed `succ_indices[t]` ← original predecessors of `t`
- reversed `pred_indices[u]` ← original successors of `u`
- `edges` rekey `(s,t) → (t,s)`, attrs cloned verbatim

New `DiGraph::reversed()` (fnx-classes) builds this in **pure integer index
space** — zero `String` hashing, zero name-table lookups, zero re-insertion.
Successor rows are appended by walking the original successor rows in
**node-major (ascending source) order**, which is exactly the order NetworkX's
`reverse()` emits edges (it walks `self.edges()` u-major and adds each `(v,u)`),
so the reversed graph's `edges()` / `succ` / `pred` iteration order is
byte-identical to nx.

`PyDiGraph::reverse` takes this fast path when **every** Python attr-mirror dict
is empty (the inner Rust attr map is then authoritative — true for all
generator/bulk-built graphs and any graph whose attrs were never fetched via
`G[u][v]`/`G.nodes[n]`). `add_node`/`add_edge` eagerly create *empty*
`node_py_attrs` dicts, so the gate checks dict **emptiness**, not map presence.
Any non-empty mirror dict (a real attr, possibly an unsynced post-creation
mutation) falls back to the unchanged, proven per-edge rebuild.

Touched: `crates/fnx-classes/src/digraph.rs` (+`reversed()`),
`crates/fnx-python/src/digraph.rs` (fast-path gate in `reverse`).

## Proof (nx-exact)
`harness_proof.py`: 20 cases — DiGraph + MultiDiGraph × 5 seeds × attrs{off,on}
(node + edge + graph attrs, parallel edges). **0 mismatches vs nx** on full
structural+attr fingerprint (nodes(data), edges(keys,data), graph dict).
Golden sha256 (identical before lever, after lever, and vs nx):
`4939d69d8b31b9c6167024e42aa42fceeabf4f1ea992806d012237c6e1dbd3bf`

`harness_adversarial.py` (the order-parity claim): scrambled insertion order ×8,
self-loops + string labels, **reverse-major insertion (worst case for pred
order)**, isolated nodes — `edges`/`succ`/`pred`/`nodes` order all == nx.

attrs=on cases exercise the slow fallback (mirror dicts non-empty); attrs=off /
generator cases exercise the fast transpose. pytest: **181 reverse tests +
3867 directed-graph tests pass**.

## Timing (warm min-of-9, gnp_random_graph(n, 0.05, directed))
| n    | E       | baseline fnx | nx     | baseline ratio | new fnx | new ratio | self-speedup |
|------|---------|-------------:|-------:|---------------:|--------:|----------:|-------------:|
| 800  | 31,926  |    84.97 ms  | 39.8ms |     1.85×      | 28.84ms |  **0.72×**|    2.95×     |
| 1500 | 112,265 |   257.33 ms  | 151ms  |     1.78×      | 161.2ms |   1.06×   |    1.60×     |
| 2500 | 312,471 |   838.21 ms  | 416ms  |     1.91×      | 480.3ms |   1.16×   |    1.75×     |

1.78–1.91× slower → **parity-to-faster** (~1.6–2.95× self-speedup). Residual at
scale is the unavoidable `edges` IndexMap build + node-table clone (O(V+E),
which nx also pays).

## Score
Impact: high (closes a 1.8–1.9× gap on a hot O(E) op, 77–358 ms saved/call;
`reversed()` reusable for `reverse_view`/transpose callers). Confidence: high
(byte-identical golden sha, 0/20 + 12 adversarial vs nx, 4048 tests). Effort:
medium (one structural method + gated wrapper, fallback preserved). Score ≥ 2.0.
