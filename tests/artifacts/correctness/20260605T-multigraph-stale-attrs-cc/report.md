# fix: MultiGraph removal purges stale mirror entries (br-r37-c1-kuxuc)

## Bug
PyMultiGraph::remove_edge cleaned edge_py_attrs/edge_py_keys with a
SINGLE key from resolve_internal_edge_key / edge_keys().last() — which
can miss the slot the mirror actually lives under (internal bucket keys
vs resolved keys, post-nj976 bucket layout). The stale dict then
silently RESURRECTS on any re-add that lands on the same internal slot:
  add_edge(0,0,label='x',weight=0.0); remove_edge(0,0);
  add_edges_from([(0,0)]) -> edge carries the OLD attrs (nx: {}).
All re-add shapes affected (auto key, explicit int key via the
fresh-int fast path, slow path with attrs — which MERGED new attrs
into the stale dict). Surfaced by the hypothesis stateful fuzz
(TestMultiGraphFuzz), reproducible at clean HEAD ef127f4b1.

## Diagnosis trail (key probes)
- slot scan: only internal slot 0 stale; key=7 re-add clean
- string-key witness: re-add at slot 0 displayed the REMOVED edge's
  public key 'K' -> both mirror maps stale, single-key removal missed
- debug-instrumented build initially PASSED -> earlier probes had run
  against a stale .so + a build including a peer's uncommitted hunks;
  re-verified against the pure tip before fixing

## Fix (one lever)
When a removal EMPTIES the (u, v) bucket, purge ALL mirror entries for
the sorted pair (retain over both maps) in addition to the targeted
single-key removal. Exhaustive-by-pair is exact regardless of which
key space the entries were stored under; partial (parallel-key)
removals keep the survivors' mirrors untouched.

## Proof
- 7-shape repro battery: attributed self-loop (the falsifying
  example), non-loop, string-key removal + int fast-path re-add,
  slow-path re-add (fresh dict, no stale merge), parallel-key
  retention, remove_edges_from, remove_node — all match nx
- TestMultiGraphFuzz: FAILS at tip -> PASSES with the fix
- MultiDiGraph probed clean (its removal path resolves consistently)
- 7 new committed tests (27 total in test_adj_row_key_parity.py)
- full pytest on the candidate tree: 21478 passed; remaining 6
  failures pre-existing (MultiDiGraphFuzz + metamorphic fixed by a
  peer's uncommitted hunks; coverage matrix + 3 unhashable ancient)
