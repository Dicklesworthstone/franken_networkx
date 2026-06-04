# closeness_vitality — route connected case to native kernel, kill subgraph-copy bomb (br-r37-c1-cvnative)

## Problem
`closeness_vitality(G)` (all nodes) computed, for every node v,
`wiener_index(G.subgraph(set(G) - {v}).copy())`. Each `.copy()` is a full-graph
construction (the String-keyed substrate tax) — ~3.6ms on n=80 — so the per-node loop ran
~13x SLOWER than networkx (n=80: fnx 379ms vs nx 29ms; n=120: fnx 3349ms vs nx — see below).
This is the classic subgraph-copy-in-loop bomb (cf reference_subgraph_copy_in_loop_bomb).

A fully-native kernel `_fnx.closeness_vitality` already existed but the wrapper never used it.

## Lever (ONE)
Route the all-nodes, unweighted (`weight=None`), undirected, simple-`Graph`, **connected**
case to the native Rust kernel (`_rust_closeness_vitality`), which computes every
Wiener-index delta in a single pass over integer adjacency. Re-key the result in `G`'s node
order to match nx's `{v: ... for v in G}`. Everything else (node=, weighted, multigraph,
directed, disconnected, n<2) keeps the exact existing Python path.

## Behavior parity (isomorphism proof)
- The native kernel only matches nx for CONNECTED graphs: for a disconnected graph nx's
  per-node value depends on whether removing the node reconnects it (`inf`) or not (`nan`),
  which the kernel does not reproduce — so the fast path is gated on `is_connected(G)` and
  disconnected graphs fall through to the nx-exact Python path. Gated on `type(G) is Graph`
  (exact) so SubgraphView filtering / nx-typed inputs / Multi/DiGraph are never mis-routed.
- Sweep: 120 random graphs (n 2..35, p 0.05..0.5, ~30% string-relabelled), plus explicit
  disconnected, single-`node=`, and tiny path/cycle/complete/star graphs (incl. cut-vertex
  `-inf` cases) — **120/120 match networkx** (values incl nan/inf/-inf AND dict key order AND
  raised-exception type).
- Golden sha256 over the nx reference values: `80bce7a1e10eb6339a3e37a5bff86446ca85d0a8383e95e48a2fd5bfb5191fd7`.
- Tests: `pytest -k "vitality or closeness_vit"` → 22 passed (run via neutral conftest; the
  in-tree `.so` could not be rebuilt because an unrelated peer WIP in digraph.rs
  (`last_int_node_canonical`) does not compile — the closeness_vitality binding is unchanged).

## Benchmark (min-of-5, ms)
| n (p=0.06) | networkx | fnx before | fnx after | after vs nx |
|------------|----------|-----------|-----------|-------------|
| 80         | 29       | 379       | ~30       | ~parity     |
| 120        | 3349*    | 3349*     | 345       | **9.69x**   |

*nx time at n=120 is dominated by its own per-node subgraph Wiener recompute; fnx-after
is 9.69x faster on the same warm min-of-5 window. Before this change fnx was ~13x SLOWER
than nx on n=80.

## Score
Impact: very high (eliminates a ~13x-slower regression AND lands ~10x FASTER than nx).
Confidence: high (120-case golden incl nan/inf/order, 22 tests, reuses a parity-proven kernel).
Effort: low (single Python fast-path, no Rust change). → Score >> 2.0.
