# br-r37-c1-dnv8g — native grid_2d_graph kernel

## Gap (warm min-of-5)
grid_2d 30x30 4.13x / 60x60 5.54x / 120x120 4.32x slower than nx.
Profile (120x120, 0.184s): 74% in two add_edges_from batches (Rust
per-edge canonicalization + dual-rep), 23% in 14400 individual add_node
PyO3 calls. The OLD native path (br-grid2d) was abandoned for emitting
"0,0" STRING labels — the display-object problem, not an algorithmic one.

## Lever (one): native one-call kernel with proper tuple display keys
- fnx_classes::Graph::grid_2d builds internals directly (complete_graph
  template): row-major all-int-tuple canonical "(i, j)" (y7m24), edges in
  nx's exact two-phase sequence INCLUDING u/v orientation, adj_indices/
  edge_index_endpoints maintained, cheap RuntimePolicy.
- _fnx.grid_2d_graph_simple wraps it with PyTuple (i, j) display keys.
- wrapper gates: create_using None + exact-int dims (bool excluded) +
  non-tuple falsy periodic; everything else takes the unchanged fallback.

## After (same bench)
30x30 0.77x / 60x60 0.71x / 120x120 0.85x — FASTER than nx.
Periodic stays 4.63x (fallback; follow-up lever noted on parent bead).
Score: ~6.5x self-speedup crossing parity => >>2.0.

## Proof
- 19-case canon matrix (nodes+attrs, edges+attrs, adjacency rows, graph
  attrs): all plain shapes incl. 0x0/1xN/Nx1, periodic bool/tuple/list
  fallbacks, create_using digraph, iterable rows, bool dims; 0 failures.
  GOLDEN_SHA256 512aab8f733daaea9273fb7f609f8224e25ba01d23bf8917af5f43bd03551927
- exact-int-tuple node keys pinned; mutation-after-build, copy,
  shortest-path on native graph, selfloop count.
- pickle: native == fallback byte-for-byte; absolute row-order-vs-nx
  divergence is PRE-EXISTING for ALL fnx graphs (filed br-r37-c1-u3qyn).
- full pytest 21546 passed, 0 failed; generator suites 1062 + 201 green.
