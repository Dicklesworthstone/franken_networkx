# pagerank / weighted-COO: integer-index edge weights + route pagerank to default-order CSR (br-r37-c1-coowt)

## Problem
The weighted CSR/COO export read each edge weight via
get_node_name(row)+get_node_name(col)+edge_attrs(&str,&str) -- two index->String
resolutions plus a String->index round-trip PER EDGE (the String-adjacency tax on
the weighted matrix path). And _pagerank_scipy's WEIGHTED branch used the nodelist
adjacency_arrays (Python nodelist canonicalisation + per-edge String index
lookups), never the integer default-order CSR.

## Lever
1. adjacency_default_order_arrays: read weights by INTEGER index pair
   (edge_attrs_by_indices(row,col)) -- no get_node_name, no String round-trip.
2. _pagerank_scipy: route the undirected weighted path to the (now integer-CSR)
   adjacency_default_order_arrays. Matrix assembly is order-independent so any COO
   order is fine; nodelist==list(G) so indices align.

## Proof
- pagerank parity 0/60 (weighted+unweighted, exact to 1e-12); weighted to_scipy +
  adjacency_matrix 0/30 byte-identical to nx; pytest 519 passed.
- Speed (min-of-15): pagerank weighted now FASTER than nx -- n=400 0.89x, n=1000
  0.84x, n=1500 ~0.68x; unweighted 0.62-0.73x. Weighted to_scipy n=1500 6.1ms vs
  nx 9.0ms.
