# adjacency_data — index-based node-key iteration (~1.29x undirected / ~1.55x directed)

Bead: br-r37-c1-xd99k (json_graph kernels) · Agent: cc · 2026-06-14

## Problem
`_fnx.adjacency_data_simple` cached node keys in a `HashMap<&str, PyObject>` and
looked up each neighbor's id object via a per-neighbor STRING-HASH
(`cached_node_key(&node_keys, py, v)`) — ~2E string hashes for an undirected
graph (every edge appears in both endpoints' adjacency rows). nx pays ~0 (its
adjacency-view neighbor keys are already PyObjects).

## Fix (one lever — same as the EdgeView edges() index lever)
Iterate by node INDEX: `keys = pg.cached_node_key_vec(py)` (nodes_seq-cached
per-index node-key Vec) + `neighbors_indices(i)` / `successors_indices(i)`
(raw `adj_indices[i]` / `succ_indices[i]` rows). The neighbor id object is
`keys[vi].clone_ref(py)` — an O(1) incref, no string hash. `keys[i]` and
`neighbors_indices(i)` walk the exact same `adj_indices[i]` row in the same order
as the old `node_keys[name]` / `neighbors_iter(name)`, so output is byte-identical.
Removed the now-dead `cached_node_key` helper.

## Proof
- Golden sha (canonical-json of fnx adjacency_data, n=40/120, undir+dir × unweighted+weighted):
  fnx-after == fnx-before, byte-identical:
  undir_unw caafeb50bf1deb24 · undir_w 9c6156123d5aacee · dir_unw 393d3eec004d6d66 · dir_w 710b79c2d15dae59
- 37 adjacency/node_link/json native-parity tests pass; 1 pre-existing unrelated
  failure (rcm-float 1e-16 in approximate_current_flow_betweenness — fails
  identically on HEAD .so).
- `cargo clippy -p fnx-python --lib` clean.

## Numbers (same-window A/B, old vs new .so interleaved, n=1500/8000, min of 25)
- undirected unweighted: 2.51ms -> 1.94ms  (1.29x self)
- undirected weighted:   4.28ms -> 3.33ms  (1.29x self)
- directed: gap to nx 1.17x -> 0.75x (now FASTER than nx)
fnx/nx gap (noise-robust): undir 1.48x->1.19x, undir_w 1.65x->1.33x.

NOTE: fnx's undirected adjacency neighbor ORDER differs from nx graph-wide
(pre-existing architectural storage-order difference, NOT this kernel — fnx F[n]
already differs from nx G[n]); this change preserves fnx's exact prior output.
