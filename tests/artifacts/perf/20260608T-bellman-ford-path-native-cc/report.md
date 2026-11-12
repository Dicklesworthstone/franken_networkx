# bellman_ford_path: native single-pair kernel — 5.41x SLOWER -> 2.1-2.2x FASTER than nx (br-r37-c1-bfpathnative)

## Problem
`bellman_ford_path(G, s, t)` delegated to nx unconditionally (full fnx->nx
conversion + nx Bellman-Ford) under a stale "Rust returns incorrect paths" note
(br-r37-c1-9axrp) — 5.41x slower than nx on a single-pair query.

## Lever (ONE): route to the native kernel; wrapper owns nx's error contract
The native single-pair kernel `_raw_bellman_ford_path` now returns nx-identical
PATHS (verified 240 directed/undirected pairs incl. negative weights + multigraph
parallel edges, 0 mismatches — the note is stale). The kernel's error
TYPES/MESSAGES diverge, so the Python wrapper owns nx's contract:
- unhashable source/target -> TypeError("unhashable type: ...") (fnx's
  `__contains__` SWALLOWS the hash TypeError, so validate via `hash()`);
- missing source -> NodeNotFound("Source ... not in G");
- unreachable OR missing target -> NetworkXNoPath("Target ... cannot be reached
  from given sources") (nx does NOT check target existence);
- negative cycle -> NetworkXUnbounded("Negative cycle detected.");
- source == target -> `[source]` BEFORE relaxation (nx short-circuits, so it
  never detects a negative cycle in that case);
- callable/non-str weight, or NaN/inf/non-numeric edge values -> delegate to nx
  (Bellman-Ford ALLOWS negatives, so a negative edge does NOT delegate). Uses the
  cached single-pass native weight scan (`_native_check_dijkstra_weights_fast`)
  so repeated queries on one graph don't re-scan every edge.

## Proof (behavior parity — absolute)
- 847+ calls (directed/undirected/multigraph, negative weights; all error cases:
  no-path, missing source, missing/unreachable target, neg cycle directed +
  undirected + src==tgt, source==target): 0 mismatches on path values AND error
  type+message.
- Golden fnx==nx over per-target path/error vectors.
- `pytest -k bellman`: 352 passed (was 5 failing on unhashable / NaN-inf /
  non-numeric weight); `-k "dijkstra or shortest_path or path_parity"`: 853 passed.

## Result (median-of-20)
| n, m        | nx       | fnx (after) | speedup vs nx |
|-------------|----------|-------------|---------------|
| 400, 2000   | 1.31 ms  | 0.60 ms     | 2.20x         |
| 1000, 5000  | 3.46 ms  | 1.67 ms     | 2.08x         |

Before: 5.41x SLOWER (delegate + fnx->nx conversion). After: 2.1-2.2x faster.

NOTE: built against the HEAD .so (a peer left fnx-python's Rust uncommitted-broken
during this session — PyMultiDiGraph/PyMultiGraph TryFrom); this change is
Python-only and uses pre-existing bindings, so it does not need a rebuild.
