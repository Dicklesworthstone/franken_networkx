# P2 scoping: construction-interior profile + rejected micro-lever

## New harness scenario: graph_build (committed)
Replicates _native_compose's storage workload in pure fnx-classes
(extend_nodes + extend_edges bulk path), pprof-able in-process.

## Interior split (pprof, N=3000 DEG=8, 1149 samples)
extend_edges = 956 samples:
- ~70%: String hashing + IndexMap machinery on the NODE/ADJACENCY maps
  (insert_full<String> 208, hash_one<&String> 186, get_index_of 184,
  adjacency get_mut 173, HashTable entry 149, sip 99, rehash 68)
- ~30%: EdgeKey pair ops (get_mut<EdgeKeyRef> 84, insert_full 80,
  hash 55+43, push_entry 43)
DESIGN CONSEQUENCE: the assumed P2 lever (NodeId-pair edge-attr
side-table) addresses only the ~30% slice. The dominant tax is the
String-keyed adjacency rows themselves.

## Rejected micro-lever (patch archived): hash-dedup in extend_edges
get_index_mut on the index-aligned adjacency map (skip 2 row-lookup
hashes/edge) + entry-API single probe on edges. Same-window A/B:
old min 6.43ms vs new min 6.76ms over 4x200 iters — WASH. The hash
cost is SPREAD across all map machinery, not concentrated in the
removed ops. Reverse-applied.

## P2 redesign (per the no-ceiling discipline: structural, not micro)
Index-primary adjacency: rows become Vec<Vec<u32>> (adj_indices is
ALREADY dual-maintained!) and the String IndexSet rows become derived/
lazy. Sequence: (a) migrate fnx-classes READERS of adjacency rows to
adj_indices (audit ~all neighbors()/neighbors_iter callers), (b) make
the String rows build-on-demand behind a revision cache (the csr_cache
pattern), (c) drop the eager String-row maintenance from the write
paths — extend_edges then writes ONE row store, killing the 70% slice.
Each step hour-sized; readers first so the flip is mechanical.
