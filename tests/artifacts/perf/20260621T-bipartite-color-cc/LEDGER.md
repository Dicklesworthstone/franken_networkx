# Perf improvement — bipartite.color/sets native adjacency snapshot 0.61x->0.79x (br-r37-c1-bipcolor)

- Agent: `BlackThrush` · 2026-06-21 · File: `python/franken_networkx/bipartite.py`

## The gap
bipartite.color (used by bipartite.sets) runs nx's BFS 2-coloring in-process but accessed
the fnx adjacency per node via G[n] (degree/isolate check) + G.neighbors(v) (BFS) — two
fnx-view materializations per node. 0.61x vs nx on complete_bipartite(50,50).

## The fix
For an exact simple FNX Graph (undirected), snapshot the key-only adjacency ONCE via the
native G._native_adjacency_keys() (yields (node, [nbrs]) in G node + neighbour order) and
run the BFS on the plain dict (neighbors = adj.__getitem__, degree = len(adj[n])). Directed
/ non-simple graphs keep the live views. Established _native_adjacency_keys lever (same as
all_triangles / WL hash).

## Verify
- BYTE-EXACT vs nx 800/800 each for color AND sets (complete_bipartite + path + cycle +
  disconnected); non-bipartite raises NetworkXError; pytest -k bipartite 1116 passed.

## MEASURED (nx/fnx, warm min-10, complete_bipartite(50,50))
| case            | before | after  |
|-----------------|--------|--------|
| bipartite.sets  | 0.61x  | 0.79x  |
| bipartite.color | ~0.61x | 0.76x  |

Improved but still <1x: residual is the pure-Python BFS (queue ops) + the is_connected
check (sets) vs nx's C-dict BFS. Full domination needs a native integer-CSR 2-coloring
kernel (Rust) — scoped follow-up.
