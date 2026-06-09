# watts_strogatz_graph: bulk extend_edges_unrecorded in the kernel — 2.0-2.4x slower -> 0.72-1.16x (br-r37-c1-wsbulk)

## Problem
watts_strogatz_graph (native path) was 2.0-2.4x slower than nx in RELEASE, even at
p=0 (no rewiring) — so the cost was the GRAPH BUILD, not the rewire. The
watts_strogatz_graph_core kernel built its final edges with per-edge
graph.add_edge(...) (each records a RuntimePolicy decision + does its own reserve).
(Note: the generator->PyGraph conversion generators.rs report_to_pygraph is already
zero-copy `inner: graph`, so it was NOT the bottleneck — an earlier attempt on the
unrelated readwrite.rs report_to_pygraph was a dead end.)

## Lever
Collect every final edge into a Vec and add them in ONE graph.extend_edges_unrecorded
call. apply_row_orders (already present) fixes each node's adjacency row to the local
order, so the bulk-insert order is irrelevant — output is byte-identical.

## Proof
- Parity vs nx 0/480 (40 seeds x k{2,4,6} x p{0,0.1,0.5,1.0}): exact node order AND
  per-node adjacency rows (G[u] order); pytest -k watts 32 passed.
- RELEASE n=1500 k=6 (min-of-15): p=0 2.37x -> 1.16x; p=0.1 2.13x -> 1.06x;
  p=0.5 1.30x -> 0.72x (FASTER than nx).
