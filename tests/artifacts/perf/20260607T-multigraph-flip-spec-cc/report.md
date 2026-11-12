# MultiGraph flip spec (br-r37-c1-s2teo)

## Current substrate (struct at lib.rs ~1871)
adjacency: IndexMap<String, IndexMap<String, IndexSet<usize>>>
           (row: neighbor-name -> parallel-key set, insertion-ordered)
edges:     IndexMap<EdgeKey, IndexMap<usize, AttrMap>>
           (string-canonical pair -> keyed bucket)
edge_count: usize (cached total)

## Target
adj_idx:   Vec<IndexMap<usize, IndexSet<usize>>>
           (per-node row: neighbor-IDX -> key set; row order preserved)
edges:     IndexMap<(usize, usize), IndexMap<usize, AttrMap>>
           (INDEX-canonical (min,max) pair -> keyed bucket)

## Census: 43 sites / 17 fns (offsets from line 1880)
WRITERS:
- add_node/_with_attrs (~236/240): adjacency.entry or_default (256)
  -> adj_idx.push(IndexMap::new()) guarded by len<nodes.len()
- add_edge_impl (~466): entry pairs 333/337 + edges.entry 340
  -> indices post-autocreate; bucket entry on (min,max) idx pair;
  row updates: adj_idx[l].entry(r).or_default().insert(key) BOTH sides
- add_fresh_edge*_unrecorded (310/322): same shape, unrecorded
- extend_nodes (375): pair at ~420ish -> push rows
- extend_keyed_edges (412, l5ve7 lever 9): bucket entry 427 -> idx pair
- auto-key computation (520/531): edge_bucket len/probe -> reads the
  NEW bucket (same logic, idx key)
REMOVERS (rekey checklist applies — BOTH paths!):
- remove_edge (633): bucket get_mut 645 + shift_remove 650 +
  remove_adjacency_key (777: row get_mut surgery) -> idx forms
- remove_node (669): O(degree) neighbor walk 682-698 + edges
  swap_remove 690 -> index rows + REKEY survivors (decrement>idx);
  adjacency.shift_remove 698 dies at P3
- remove_nodes_from: NOT FOUND in Multi impl?? VERIFY — may inherit a
  retain-based path elsewhere; if absent, only single-removal rekey
READERS:
- edge_keys (140): adjacency.get(l)?.get(r) -> adj_idx[li].get(&ri)
- neighbors (166) / degree (220/221: sums key-set lens) -> index rows
- edges_ordered/borrowed (705/737): u-major row walks -> index walks
  (names via get_index; NOTE the unit tests at 837/865 assert
  TRAVERSED ORIENTATION — keep emission orientation = walk side)
- snapshot (761): derive via names
REORDERERS:
- reorder_rows_for_nx_copy_walk (23): String rows -> pure integer
  (Graph recipe; row VALUE maps must reorder too — the nested
  IndexMap<usize, IndexSet> reorders by OUTER key order only)
- apply_row_orders (58): integer per-row reorder + key-set carry
PyO3 LAYER (fnx-python lib.rs): edge_py_attrs/(String,String,usize)
keys + py_edge_key/resolve_internal_edge_key STAY STRING-KEYED this
phase (mirror keys are display-layer; flip later if profiled).

## Checklist (from the 4 prior flips)
[] oracle FIRST (debug_index_rows_consistent comparing nested rows,
   order included) before trusting writer patches
[] REKEY BOTH removal paths (decrement-above-idx + remap)
[] regexes scoped to impl region ('pub struct MultiGraph {' brace)
[] accessor audit AFTER the key flip (edge_attrs_by_indices twin for
   keyed buckets: bucket_by_indices(l,r) -> Option<&IndexMap>)
[] edges_ordered orientation tests (837/865) are the parity pins
[] edge_count cache: verify every bucket mutation maintains it

## Phases
P1 adj_idx + writers + oracle (one session)
P2 readers (one session)
P3 delete String rows + edges-key flip + rekey (one session)
MultiDiGraph: repeat with succ/pred split + ORIENTED edge keys.

## REVISION (post TealSpring Pass-12 rejection, ed3113a6f)
The phased rows-first sequencing is WRONG for Multi: TealSpring's
candidate (index rows + String buckets kept) regressed every scenario
(ctor 0.088->0.161s, hyperfine 0.66x, cProfile 4.4->6.7s). Multi's
per-edge work funnels through the BUCKET table (key resolution per
edge); index rows add dual-write cost without removing the bucket tax,
and Multi's readers are bucket-centric so P2 reader wins don't offset.
EITHER flip rows+buckets ATOMICALLY (readers migrated same-arc) OR the
batch-local constructor kernel route — which TealSpring has claimed
(progress file Pass 12 next target: intern endpoints once, commit
rows+buckets without per-edge probes, target keyed ctor <=1.50x).
LANE YIELDED to TealSpring; cc pivots to 1l8s0 (dijkstra residual).
