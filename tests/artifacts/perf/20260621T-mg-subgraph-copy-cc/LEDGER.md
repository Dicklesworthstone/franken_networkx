# MultiGraph.subgraph(nodes).copy() 0.72x — construction-substrate-bound (keyed 4-tuple batch miss)

- Agent: `CopperCliff` · 2026-06-21 · MEASURED · **REJECT (no my-file lever; substrate-bound)**
- No source change shipped. Diagnostic + negative evidence only.

## Measured (warm min-of-11, MultiGraph N=900, 3600 edges, keep 400 nodes; this host)
- `G.subgraph(sub).copy()`: fnx **6.05ms vs nx 4.06ms = 0.72x** (LOSS).
- For contrast, FULL `G.copy()` BEATS nx: fnx 5.19ms vs nx 8.27ms (1.59x) — native `_native_copy`.

## Root cause (precise)
`_FilteredGraphView.copy()` (__init__.py ~38360) bails the native induced fast
path for multigraphs (`_copy_induced_simple_fast` returns None when
`is_multigraph()`), so it rebuilds via
`result.add_edges_from((u,v,key,dict(attrs)) for ... in self.edges(keys=True,data=True))`.
- The 4-tuple `(u,v,key,data)` edges have EXPLICIT keys. The native multigraph
  batch `_try_add_attr_edges_from_batch` REJECTS this shape (verified: returns
  False, 0 edges added) — it only handles auto-key 2/3-tuples on a fresh graph.
- So construction falls to the per-edge Python loop: 44400 `add_edge` calls +
  44400 `get_edge_data(...).update()` calls (2 PyO3 round-trips/edge). That is
  the entire 0.72x gap.
- list-vs-generator makes NO difference (both 10.2ms) — the batch is missed on
  shape, not iterability.

## Routes ruled out (negative evidence)
1. **Materialize generator → list** before add_edges_from: no change (batch
   rejects 4-tuples regardless of list/gen). See `batch_probe.py`.
2. **`_native_copy()` + `remove_nodes_from(complement)`** (reuse the fast full
   copy then drop the 500 non-kept nodes): byte-identical to nx AND official
   (node/edge/key/attr/graph-attr signature match), but SLOWER — 6.90ms (the
   multigraph `remove_nodes_from` of 500 nodes costs ~1.7ms on top of the 5.2ms
   native copy). Not a win. See `route_probe.py`.

## Conclusion / the only viable lever
Beating nx here requires a NATIVE keyed-4-tuple batch construction kernel
(`(u,v,explicit_key,data)` on a fresh MultiGraph/MultiDiGraph) — i.e. extend
`_try_add_attr_edges_from_batch` (crates/fnx-python/src/lib.rs for PyMultiGraph,
digraph.rs for PyMultiDiGraph) to accept explicit keys with collision-faithful
key assignment, then route `_copy_induced_simple_fast` through it for multigraphs.
That is a Rust change spanning two files currently under another agent's
uncommitted edits, with subtle parallel-edge key-parity risk, and the install
here is stale (full rebuild required to verify). Deferred as a scoped Rust bead
rather than attempted on a dirty shared tree. The gap is the documented
multigraph dual-storage (AttrMap + Python mirror) construction substrate, not a
wrapper inefficiency that a my-file Python change can close.

Related: [[reference_multigraph_attr_batch_construction]] (the existing 2/3-tuple
batch), [[reference_tonumpy_dirty_weight_ceiling]] (same dual-substrate ceiling),
[[reference_subgraph_copy_in_loop_bomb]].
