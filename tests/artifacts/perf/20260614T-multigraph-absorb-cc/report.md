# Native MultiGraph(Graph) absorb kernel — 2.07x slower → parity (unweighted) / 1.39x (weighted)

Bead: br-r37-c1-1o74q
Agent: cc / 2026-06-14

## Problem

`MultiGraph(g)` (converting a simple graph to a multigraph) was ~2.1–2.6x slower
than nx — the per-edge Python `add_edges_from((u, v, 0, attrs))` rebuild (the
explicit-key 4-tuple form bails to the per-edge `add_edge` loop). DiGraph(Graph)
already had a native `digraph_absorb_graph_bidirected` fast path; MultiGraph had
no equivalent.

## Fix (native absorb kernel, sibling of digraph_absorb)

Added `_fnx.multigraph_absorb_graph` (crates/fnx-python/src/readwrite.rs): builds
the MultiGraph inner directly from the simple source's `edges_ordered_borrowed()`
(node-major canonical order == `source.edges()`, so adjacency order is
byte-identical), assigning key 0 to every edge (a simple source has one edge per
pair). Routed from `_copy_constructor_graph_source` for `MultiGraph(Graph)`,
alongside the existing DiGraph(Graph) fast path.

Two mirror optimisations make it actually fast (a naive port was still ~1.8x):
- **edge attrs: lazy, not eager.** `ensure_edge_py_attrs` rebuilds the Python
  edge dict from the inner core (`attr_map_to_pydict`) on demand, so for every
  value that round-trips (no `__fnx_incompatible` marker) the eager
  `edge_py_attrs` mirror is redundant — skipped, saving ~|E| PyDict allocs +
  HashMap inserts. Verified the lazily-materialised dict is live + writable.
- **empty node attrs stay sparse** (no empty-PyDict-per-node). Non-empty node
  attrs are mirrored eagerly because `ensure_node_py_attrs` only makes empty
  dicts (no core rebuild). `edge_py_keys` left empty — `py_edge_key` lazily
  returns `PyInt(0)`, the key every edge carries. Non-round-tripping attrs bail
  to the Python path.

## Proof

- 50-seed parity sweep (unweighted / scalar-weight / multi-attr+node-attr,
  isolated nodes), comparing keyed edges + node attrs + per-node adjacency vs nx,
  reading edge data to force lazy materialisation — **0 mismatches**.
- Golden (MultiGraph from gnp 40,0.15,seed=7, weighted): keyed-edge sha256
  `4069e023906f6e3a…`, identical before/after the mirror optimisation.
- Full suite (remote, kernel confirmed present): only the 6 known pre-existing.

## Timing (interleaved min, N=1000 p=0.02)

| op | before (4-tuple) | after (native absorb) | nx | vs nx |
|----|------------------|-----------------------|-----|-------|
| MultiGraph(Graph) unweighted | ~2x | 17.5ms | 18.3ms | **1.04x (parity)** |
| MultiGraph(Graph) weighted | 38.1ms (2.07x) | 30.2ms | 21.7ms | 2.07x → **1.39x** (1.26x self) |

Unweighted is now at parity; weighted halved. Residual weighted cost is the
per-edge `py_dict_to_attr_map` (reading the Python edge dict as the source of
truth); a clone-core-with-sync fast path for scalar-only attrs is a follow-up.
