# condensation: integer-CSR edge walk (br-r37-c1-cond-csr)

## Problem
`condensation(G)` (native `condensation_nx_ordered`) was 2.99x SLOWER than nx
(17ms @ n=2000/m=12000). The condensation edge loop iterated
`dg_ref.edges_ordered()` — which CLONES every edge's AttrMap + endpoints — and
then hashed the String endpoints (`canonical_to_scc.get(&edge.left)`) per edge,
even when all edges collapse into one SCC (the common dense case).

## Lever (ONE)
Walk the integer successor rows (`successors_indices(u_idx)`) in source-major
order — exactly nx's `for u, v in G.edges()` order — and index the SCC map by
integer node index (`scc_of: Vec<usize>`) instead of hashing String endpoints.
No AttrMap clones, no String hashing. Same edge set, same first-seen dedup, same
order => byte-identical condensation DAG.

## Proof (behavior parity — absolute)
- 60 random graphs (DiGraph + MultiDiGraph + self-loops): 0 mismatches across
  nodes, edges, per-node `members` sets, and `graph['mapping']`.
- Golden sha256 over a 5-graph corpus (nodes/edges/members/mapping): fnx == nx
  (`56e66910...`).
- `pytest -k "condensation or strongly_connected"`: 415 passed.

## Result (median-of-5)
| n, m         | nx       | fnx (after) | speedup vs nx |
|--------------|----------|-------------|---------------|
| 2000, 12000  | 5.50 ms  | 2.48 ms     | 2.22x         |
| 4000, 24000  | 14.76 ms | 4.34 ms     | 3.40x         |

Before: 2.99x SLOWER than nx. After: 2.2-3.4x faster (gap grows with |E| as the
AttrMap-clone tax scales).
