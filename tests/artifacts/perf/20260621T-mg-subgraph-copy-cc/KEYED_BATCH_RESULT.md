# Follow-up: native keyed-4-tuple batch BUILT + MEASURED — still loses to nx (dual-storage ceiling)

- Agent: `CopperCliff` · 2026-06-21 · MEASURED · **REJECT (built, verified, reverted)**

The prior LEDGER.md deferred the "native keyed-4-tuple batch" lever to a bead.
I then actually implemented and measured it (clean worktree off origin/main,
full release build) rather than leaving it speculative. Result: conclusive reject.

## What was built
- `_try_add_keyed_attr_edges_from_batch` on `PyMultiGraph` (crates/fnx-python/src/lib.rs):
  explicit-key 4-tuple `(u,v,key,data)` batch on a fresh MultiGraph, inserting
  each edge under its GIVEN integer key via `extend_keyed_edges_with_attrs_unrecorded`
  (preserves gapped parent keys — auto-key batch could not).
- Wrapper gate in `_multi_add_edges_from` + materialize `_FilteredGraphView.copy()`
  4-tuple generator to a list so the batch fires.

## Correctness — PASSED
72/72 `subgraph().copy()` byte-identical to NetworkX across MultiGraph +
MultiDiGraph (MDG via correct per-edge fallback), gapped keys (post-removal),
self-loops, edge/node/graph attrs, full/half/stride node subsets.

## Performance — STILL LOSES (the reject reason)
- `MultiGraph.subgraph(range(400)).copy()` N=900/3600e: `0.86–0.90x` vs nx
  (improved from the 0.72x baseline, but still < 1.0x).
- Larger subsets (keep 600) reach ~parity `0.98–1.02x` (overlapping CIs).
- **Direct `MultiGraph().add_edges_from([3576 4-tuples])`: `0.70x` vs nx** — the
  batch FIRES (per-edge loop eliminated) yet still loses.

## Root cause (conclusive)
The batch removes the per-edge `add_edge` loop but each edge still pays
`py_dict_to_attr_map` to convert its Python data dict into a Rust `AttrMap`
AND retains the Python dict as a mirror (dual storage). That per-edge conversion
costs MORE than NetworkX's single-dict `keydict[key] = datadict` assignment.
This is the same dual-`AttrMap`+mirror multigraph construction ceiling the
existing 2/3-tuple `_try_add_attr_edges_from_batch` already hits (0.8–0.9x vs nx,
documented). A keyed variant cannot escape it.

## Verdict
Reverted (not shipped). Beating nx on multigraph attributed construction —
subgraph copy included — requires eliminating the dual storage (a lazy `AttrMap`
that defers Python→Rust conversion until a native kernel actually reads attrs),
which is a deep substrate change, NOT a keyed-batch addition. Bead
`br-r37-c1-mg-subgraph-keyed-batch-z1q8i` closed as no-ship; the real lever is the
lazy-AttrMap substrate (see [[reference_multigraph_attr_batch_construction]]).
