# EdgeView `edges(data="attr")` — index-based node-key iteration: gap to nx 1.59x → 1.26x (N=2000), 1.29x → 1.11x (N=3000)

Bead: br-r37-c1-2a00r (substrate lever, part 3 of N)
Agent: cc / 2026-06-14

## Problem

The `data="weight"` (Attr) and AttrWithDefault paths in `EdgeView.__iter__`'s
general `_ =>` branch still hashed the canonical String per edge endpoint
(`g.py_node_key(left)` + `g.py_adj_key(left, right)`), unlike the NoData
(ecc1c5e8c) and AllData (2c6a48e2a) paths which now use index keys.

## Fix (one lever: widen the index fast path to all non-AllData variants)

Generalized the `__iter__` index fast path from NoData-only to **every
non-AllData variant** (NoData / Attr / AttrWithDefault). When `adj_py_keys` is
empty: build the node-index → key-object Vec once (`cached_node_key_vec`) +
`nodes_ordered()`, walk `edges_ordered_indices()`, clone_ref `keys[u]`/`keys[v]`
directly. The Attr value is read via the unchanged
`edge_py_attrs.get(edge_key(nodes[u], nodes[v]))` → `get_item(attr)` (immutable
borrow, so no `&mut` needed). Non-empty `adj_py_keys` (z6uka) still falls
through to the exact per-edge `py_adj_key` path.

## Proof (deterministic — load-independent)

- Data-variant sweep (60 seeds: data=True / data="weight" / data="color"+default
  / NoData / data="missing" / nbunch, weighted+multi-attr): **0 mismatches**.
- Golden `edges(data=True)` sha256 `22a55fb648750669…` == nx (unchanged);
  NoData golden `2fc3fbeb0574b09b…` still 0 fails.
- Suite: 6155 passed, only the 2 known pre-existing fails (rcm-float, gexf).

## Timing (interleaved min-of-9, warm)

| op | before | after | nx | vs nx |
|----|--------|-------|-----|-------|
| edges(data="weight") n=2000 | ~11.2ms | 9.24ms | 7.34ms | 1.59x → **1.26x** |
| edges(data="weight") n=3000 | ~11.1ms | 9.77ms | 8.82ms | 1.29x → **1.11x** |

## Residual (2a00r, still open)

The `edge_py_attrs` `edge_key` String-tuple probe (2 allocs/edge) is the last
per-edge String tax across all data paths — needs index-keyed attr storage
(~50-site refactor) to fully reach/beat nx. Also: `NodeViewIterator.__next__`
per-element FFI mutation guard; `dict(G.adjacency())` 1.77x.
