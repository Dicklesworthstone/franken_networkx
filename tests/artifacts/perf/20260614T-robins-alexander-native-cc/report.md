# Native robins_alexander_clustering — delegated → 0.01x (≈100x faster than nx)

Bead: br-r37-c1-niit0
Agent: cc / 2026-06-14

## Problem

`fnx.bipartite.robins_alexander_clustering` was re-exported from networkx
(`from ...bipartite import *`), so it ran nx's `@nx._dispatchable` version — full
`_fnx_to_nx` conversion (O(V+E)) followed by nx's `_four_cycles` / `_threepaths`
counters that build Python `set` unions/intersections per node. ~1.1x slower than
nx on a native graph, and bound to nx's slow set-based counting.

## Fix (native integer-CSR count kernel)

`CC_4 = 4·C_4 / L_3` where `C_4` (four-cycles) and `L_3` (three-paths) are
**integer graph invariants** — order-independent. Added a native kernel
`_fnx.robins_alexander_counts(G)` (crates/fnx-python/src/algorithms.rs) that
computes both raw integer counts over the integer CSR adjacency
(`neighbors_indices`) using reusable mark arrays:

- `_four_cycles`: for each v, second-order neighbours x not yet `seen`, add
  `p2*(p2-1)` with `p2 = |N(v) ∩ N(x)|` (mark-array intersection).
- `_threepaths`: for each v, u∈N(v), w∈N(u)\{v}, add `|N(w)\{v,u}|` = `deg(w) -
  1 - [v∈N(w)]` (u∈N(w) always holds since w∈N(u); `v∈N(w) ⟺ w∈N(v)` via a mark
  of N(v)).

The kernel returns the two RAW integer numerators; the Python wrapper does the
exact same float arithmetic as nx — `(4.0 * (c4_numer/4)) / (l3_numer/2)` — so
the result is **byte-identical**. No node-order matching needed (counts are
invariants). Directed / multigraph / nx-typed inputs delegate to nx.

## Proof

- 60-seed random bipartite-graph sweep (varied sizes incl. empty/degenerate):
  result `== nx` (exact float equality) — **0 mismatches**.
- Named graphs: davis_southern_women `0.46776406035665297` (==nx), `K_{3,3}`=1.0,
  `K_{2,2}`=1.0, path_graph(4)=0.0, empty graph → int `0` (type parity: int 0 vs
  float, both match nx). The native counts equal nx's `_four_cycles*4`/
  `_threepaths*2` exactly (davis: 1364 / 5832).
- Golden sha256 of the 60-case value vector: `dbf642a606d62f54…`.
- Targeted bipartite/cluster suite: 883 passed (1 known pre-existing chordal
  failure). Full suite (remote, kernel confirmed present): 22265 passed, only the
  6 known pre-existing failures.

## Timing (min-of-8)

| size (top×bottom/edges) | before (delegated) | after (fnx) | nx | now vs nx |
|-------------------------|--------------------|-------------|-----|-----------|
| 150×120 / 1200 | ~23ms (≈1.1x) | 0.22ms | 23.1ms | **0.01x (≈105x)** |
| 400×300 / 4000 | — | 1.00ms | 126.8ms | **0.01x (≈127x)** |

The native integer-CSR kernel replaces nx's per-node Python set unions/
intersections; ~100x faster and byte-exact. Score ≫ 2.0.
