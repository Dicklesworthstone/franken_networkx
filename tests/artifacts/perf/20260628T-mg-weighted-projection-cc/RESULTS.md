# MultiGraph weighted-shortest-path projection — strict work-removal — CopperCliff 2026-06-28

## Problem
single_source_dijkstra_path_length on a weighted MultiGraph ran at ~0.13x vs nx
(n=5000/15k edges: fnx 153-233ms vs nx 18-30ms). The dijkstra itself is the fast
simple-graph kernel; the cost is `multigraph_to_weighted_simple_graph` — the
min-parallel-weight projection rebuilt EVERY call.

## Fix (algorithms.rs, br-cc-mgproj — strict work-removal, identical output)
Old body: `mg.edges_ordered()` TWICE (each deep-clones every parallel edge into an
owned MultiEdgeSnapshot: String endpoints + AttrMap) + per-edge `add_edge_with_attrs`
(each pushes a change-ledger entry). New body: iterate `edges_ordered_borrowed()`
ONCE (no per-edge clones), select min-weight parallel edge per pair, bulk
`extend_edges_with_attrs_unrecorded` the survivors (no ledger). Only SELECTED edges'
attrs are cloned (<= edge_count vs 2x all). Same nodes/attrs, same survivor edges in
same order, same apply_row_orders => byte-identical output for every consumer.

## Measured
MG dijkstra path_length: n=5000 0.13x->0.30x ; n=10000 0.11x->0.28x  (2.3-2.5x self)
Byte-exact: 0/120 (path_length + path; weighted MultiGraph incl parallel edges +
selfloops + dirty/clean builds) == nx. 4366 shortest-path/multigraph tests pass.

## Residual (NOT a win yet)
Still ~0.3x vs nx: building a full Graph projection per call is inherently heavier
than nx's direct multigraph walk (min-over-parallel-edges weight function during
relaxation). A full win needs a NATIVE multigraph dijkstra kernel that runs on the
MG store directly (CSR + min-parallel-weight), bypassing Graph construction.
Documented as the next lever. This commit is a strict work-removal (2.3x less work,
identical output) benefiting the whole MG-weighted shortest-path family.
