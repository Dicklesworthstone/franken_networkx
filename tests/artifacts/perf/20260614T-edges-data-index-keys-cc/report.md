# EdgeView `edges(data=True)` — index-based node-key iteration: 9.45ms → 7.10ms (1.33x self), gap to nx 1.66x → 1.24x

Bead: br-r37-c1-2a00r (substrate lever, part 2 of N)
Agent: cc / 2026-06-14

## Problem

After part 1 (NoData `edges()`, ecc1c5e8c), the `data=True` path still hashed
the canonical String per edge endpoint: `edge_alldata_items` (views.rs) called
`edgeview_py_node_key(node_key_map, left/right)` per edge — a
`HashMap<String,PyObject>` lookup per endpoint. A node of degree d was hashed
~d times across its incident edges.

## Fix (one lever: same index path, in `edge_alldata_items`)

When `adj_py_keys` is empty (uniform adjacency-row objects), build the
node-index → Python key-object Vec ONCE (`nodes_ordered()` mapped through
`edgeview_py_node_key`), then walk edges via `edges_ordered_indices()` (added in
part 1) and clone_ref `key_vec[u]` / `key_vec[v]` directly — O(1) incref, no
per-endpoint String hash. The `edge_py_attrs` `edge_key(left,right)` String
probe is unchanged (re-keying that map by index is a separate, larger lever).
Non-empty `adj_py_keys` (br-r37-c1-z6uka) falls through to the exact per-edge
path. nbunch filtering preserved (checks `nodes[u]`/`nodes[v]`).

## Proof (deterministic — load-independent)

- Data-variant sweep (60 seeds, data=True / data=attr / data=attr+default /
  NoData / missing-attr / nbunch, weighted+multi-attr): **0 mismatches** vs nx.
- Live-dict identity preserved (mutation through the yielded dict reflects on
  the graph); empty / single-node OK.
- Golden `edges(data=True)` (gnp 300,0.03,seed=7): sha256 `22a55fb648750669…`,
  equals nx, **unchanged** before/after.
- NoData path (part 1) re-verified: 80-seed key-type sweep + golden
  `2fc3fbeb0574b09b…` still 0 fails.
- Suite: 4921 passed, only the 1 known pre-existing gexf classification fail.

## Timing (interleaved min-of-9, weighted, warm)

| op | before | after | nx | self | vs nx |
|----|--------|-------|-----|------|-------|
| edges(data=True) n=2000 (~20k E) | 9.45ms | 7.10ms | 5.74ms | **1.33x** | 1.66x → **1.24x** |
| edges(data=True) n=3000 | ~12.5ms | 9.85ms | 7.09ms | ~1.27x | 1.75x → **1.39x** |

## Residual (2a00r, still open)

- `edges(data=attr)` (data="weight") still on the old inline Attr path (~1.3x) —
  same index treatment applies, separate code path.
- The `edge_py_attrs` `edge_key` String-tuple probe (2 allocs/edge) — needs
  index-keyed attr storage (~50-site refactor) to fully close.
- `NodeViewIterator.__next__` per-element FFI mutation guard.
- `dict(G.adjacency())` 1.77x (same root cause + edge-dict tax).
