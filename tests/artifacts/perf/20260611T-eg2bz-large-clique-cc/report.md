# br-r37-c1-eg2bz — approximation.large_clique_size de-delegation (2.2-2.4x vs nx)

## Problem
`fnx.approximation.large_clique_size` resolved through `_ApproximationNamespace.
__getattr__`, which round-trips the graph through `_networkx_graph_for_parity`
(a full O(V+E) fnx→nx build) before running nx's Pattabiraman degree-greedy
heuristic — ~2x slower than nx, dominated by that conversion.

## Lever
De-delegate: run nx's EXACT heuristic in-process over a cheap key-only native
adjacency snapshot (`_native_adjacency_keys`) — no full nx.Graph build. The
algorithm only needs a degree map + adjacency sets. It is set-iteration-order
dependent (`max(U, key=degree)` ties), so the snapshot is keyed by the original
node **objects**; CPython set order then matches nx's exactly → byte-identical
result. Directed / multigraph keep nx's `@not_implemented_for` raise via
delegation. Added as a concrete method on `_ApproximationNamespace`.

## Result
| n    | new (in-proc) | delegated (old) | genuine nx | vs delegated | vs nx |
|------|---------------|-----------------|------------|--------------|-------|
| 300  | 1.53 ms       | 7.27 ms         | 3.68 ms    | 4.76x        | 2.41x |
| 600  | 5.37 ms       | 24.79 ms        | 11.86 ms   | 4.62x        | 2.21x |
| 1000 | 10.57 ms      | 51.35 ms        | 23.60 ms   | 4.86x        | 2.23x |

## Proof
- Parity vs genuine nx over **260 cases** (60 seeds × 5 adversarial generators —
  gnp dense/very-dense, barabasi, watts, powerlaw — stressing the
  `max(U, key=degree)` set-order tie-break + 20 string-keyed): **0 fails**.
- Directed & multigraph both raise `NetworkXNotImplemented` (matches nx).
- `tests/python -k "large_clique or approximation"`: 216 passed, 0 failed.

## Note
Found the contested `__init__.py` was stale (last modified ~9h ago, origin
advanced 4+ commits since) — i.e. abandoned working-tree cruft, not active
contention — so this `_ApproximationNamespace` edit was safe to land via a
worktree on clean origin/main.
