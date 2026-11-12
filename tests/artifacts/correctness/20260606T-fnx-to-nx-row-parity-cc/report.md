# br-r37-c1-w7nn3 — _fnx_to_nx adjacency-row parity (order + objects)

## Bug
The conversion's succ-major edge emission preserves SUCC rows but:
- fills directed PRED rows in walk order (nx-native pred rows follow
  edge insertion) — POISONING every delegated directed algorithm whose
  result depends on pred iteration (found because the 'safe' nx
  delegation for bidirectional_shortest_path returned the wrong
  tie-break path);
- reverse-direction cells took the emitted endpoint object instead of
  the source's row display object (z6uka mixed-key overrides) —
  also true for succ cells via the bulk path's node-map mapping.

## Fix
1. Bulk path emits neighbor ROW objects (fg[obj] iteration).
2. Post-pass _align_rows rebuilds every adjacency inner dict in the
   source's row order with the source's row objects (identity-guarded;
   inner datadicts reused so nx's _adj/_succ/_pred sharing invariant
   holds — pinned by tests).

## Proof
4-class pinned battery (tie diamond + isolated + mixed keys + parallel
edge) + 60-trial random corpus + datadict-sharing pins + the e2e
formerly-poisoned delegation: 0 failures
(golden sha f17d5928e4b2d8932188d00419a85af9d826fd1fd65b27eb2e8c864e581a9473).
Conversion cost 12k-edge digraph: 65.9ms (O(V+E) identity-check
post-pass). Full pytest 21642 passed, 0 failed.
