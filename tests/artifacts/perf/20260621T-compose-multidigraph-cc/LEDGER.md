# Perf WIN — compose(MultiDiGraph) native keyed-with-data batch: 0.36x -> 0.67x (br-r37-c1-mgcompose)

- Agent: `BlackThrush` · 2026-06-21 · Files: `crates/fnx-python/src/digraph.rs`, `__init__.py`
- Closes the compose gap scoped in the session scorecard (c778f06f0).

## The gap
compose multigraph branch did `out.add_edges_from((u,v,key,dict(d)) ...)` TWICE (G then H).
4-tuple keyed edges are REJECTED by every native add_edges_from batch -> per-edge
add_edge_with_key_and_attrs (2 record_decision/edge). G's add is fresh but H's runs on a
non-fresh graph, so even routing only G left H per-edge-bound (0.36x->0.37x, negligible).

## The fix
1. Native `_native_add_keyed_edges_with_data` on PyMultiDiGraph — the with-data sibling of
   `_native_add_keyed_edges_no_data`: user key = display key, internal key = per-pair auto
   counter, attrs parsed + lazy mirror (no eager empty dicts). Fresh-gate + bail (Ok(false))
   on any non-4-tuple/duplicate so the per-edge loop keeps every contract.
2. compose pre-merges G's then H's keyed edges in Python (H's data UPDATES a shared
   (u,v,key) in place, new H edges append — exactly nx's second add_edges_from), yielding
   each (u,v,key) ONCE in G-then-H-new order, then ONE fresh native batch. MultiGraph lacks
   the native method (getattr->None) and falls through to add_edges_from unchanged.

## Verify
- BYTE-EXACT vs nx 3000/3000 robust (incl overlap-with-overwrite, custom keys, str nodes,
  empty H): nodes + edges(keys,data) + succ AND pred adj order + node attrs. MultiGraph
  compose falls through correctly. clippy clean; pytest -k 'compose/multidigraph/operator/
  union/disjoint/convert' 2343 passed.

## MEASURED (nx/fnx, warm min-8, n=300)
| case                              | before | after  |
|-----------------------------------|--------|--------|
| compose(MultiDiGraph) overlapping | 0.36x  | 0.67x (99->46ms) |
| compose(MultiDiGraph) disjoint    | —      | 0.57x  |

~2x faster; still <1x — residual is the Python edge_map pre-merge (2x edges() materialize +
dict ops). To dominate, move the overlap-merge into the native batch (Rust) — scoped follow-up.
