# node_link_data — index-based node-key iteration (~1.91x undirected / ~1.46x directed)

Bead: br-r37-c1-xd99k · Agent: cc · 2026-06-14

## Problem
`_fnx.node_link_data_simple` called `py_node_key` DIRECTLY twice per edge
(source + target) — a HashMap<String,PyObject> string-hash each — plus a
`HashSet<String>` seen-set for the undirected dedup. ~2E string hashes + per-node
String clones. nx pays ~0 (adjacency keys are PyObjects).

## Fix (one lever, same as adjacency_data_simple)
keys = cached_node_key_vec(py) (per-index node-key Vec) + neighbors_indices(i) /
successors_indices(i). Endpoint key = keys[i]/keys[vi].clone_ref (O(1) incref, no
hash). Undirected dedup uses a `vec![false; n]` seen[vi] (finished source
indices) — byte-identical to the prior HashSet<String> of finished source names.

## Proof
- Golden sha (canonical-json, n=40/120, undir+dir × unweighted+weighted):
  fnx-after == fnx-before byte-identical AND == nx (node_link_data dedups edges,
  so order-clean): 2c4948af2730ecdb / c5202a412abe2aca / d6f2c6fc61d093e6 / c9342084e43f1ce7
- node_link/json/adjacency native-parity tests pass; clippy clean.

## Numbers (same-window A/B old vs new .so, min of 25)
- undirected unweighted (n=1500/8000): 2.28ms -> 1.19ms  (1.91x self)
- undirected weighted:                 2.84ms -> 1.65ms  (1.72x self)
- directed (n=1200/6000):              1.20ms -> 0.82ms  (1.46x self)
fnx now faster than nx on all four shapes.
