# perf: incremental edge_index_endpoints in Graph::remove_edge (watts/generators)

## Lever
`fnx_classes::Graph::remove_edge` rebuilt the ENTIRE `edge_index_endpoints`
vector on every single edge removal via `rebuild_edge_index_endpoints()` — an
O(|E|) pass that does a `nodes.get_index_of()` HashMap lookup for every
remaining edge. A remove-heavy construction like `watts_strogatz_graph`
(rewires ~p·|E| ring edges, each a `remove_edge` + `add_edge`) was therefore
O(|E|^2) with a hashing constant.

`edge_index_endpoints` is maintained strictly PARALLEL to the `self.edges`
IndexMap (one entry per edge, same insertion order — pushed once per add in
`add_edge_with_attrs` / `extend_edges_unrecorded`). So a removal only needs to
drop the single entry at the removed edge's position. Use
`IndexMap::shift_remove_full` to get that position, then
`edge_index_endpoints.remove(pos)`. Bit-identical to a full rebuild (the
parallel vector ends up exactly as the rebuild would leave it), but eliminates
the per-edge hashing rebuild. The remaining O(|E|) per remove is the IndexMap's
own order-preserving `shift_remove` shift — inherent and unchanged.

## Correctness (byte-exact)
240-case differential vs networkx (n in {20,50,100,200} x k in {4,6,8} x p in
{0.0,0.1,0.3,0.5,1.0} x 4 seeds; p=1.0 = every edge rewired = max remove stress),
0 mismatches on EXACT edge order + node order. golden sha d13d5dfb...
fnx-classes cargo tests: 61 passed. Full Python suite: see suite log.

## Perf (warm min-of-8)
| case                  | before   | after   | self-speedup | vs nx (after) |
|-----------------------|----------|---------|--------------|---------------|
| watts n=500 k=6 p=0.1 | 12.37ms  | 3.22ms  | 3.84x        | 2.60x         |
| watts n=500 k=6 p=0.5 | (≈O(E^2))| 6.35ms  | —            | 3.81x         |
| watts n=1000 k=6 p=0.1| —        | 8.57ms  | —            | 3.93x         |
| connected_watts 500   | —        | 3.24ms  | —            | 2.54x         |

watts_strogatz went from 12.45x slower than nx to 2.6x. Broad win: every
remove_edge-heavy path (operators, edge removals, rewiring generators) benefits.
The residual vs-nx gap is the shared report_to_pygraph PyDict-alloc construction
tax (blocked behind the locked PyGraph attr-dict model, br-r37-c1-w1dm8).
