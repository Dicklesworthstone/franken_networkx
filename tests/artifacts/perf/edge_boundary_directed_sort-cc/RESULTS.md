# edge_boundary_directed — remove stray result.sort() (parity bug + perf)

## Lever (br-r37-c1-tep7r)
The native edge_boundary_directed kernel ended with result.sort(), but
nx.edge_boundary emits boundary edges in nbunch1-iteration x successor-adjacency
order (its OutEdgeView order), NOT sorted. The sibling undirected edge_boundary
already returns unsorted. The stray sort made directed edge_boundary(data=False)
diverge from nx on order. Removed it.

## Correctness
edge_boundary vs nx across 768 cases (simple/directed/multi/multidi x nbunch2 x
data x default): 16 mismatches -> 0 (all 16 were this directed-sort divergence).
golden sha (directed data=False) reproducible; 115 boundary/cut_size/volume tests
pass.

## Benchmark (warm min) — directed edge_boundary(data=False), ratio = nx/fnx
| n    | fnx      | nx       | nx/fnx |
|------|----------|----------|--------|
| 400  | 0.415ms  | 0.469ms  | 1.13x  |
| 800  | 1.634ms  | 1.711ms  | 1.05x  |
| 1500 | 4.937ms  | 5.141ms  | 1.04x  |

Removing the O(B log B) sort flips directed edge_boundary from slower-than-nx
(0.99x, with sort) to faster-than-nx with CORRECT nx order. Closes the last-
session residual (the "16 pre-existing mismatches" noted in br-r37-c1-wpyzi).
