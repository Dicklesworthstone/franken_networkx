# pagerank (DiGraph): directed integer-CSR default-order COO — unweighted 2x-slower->FASTER, weighted 3x->1.9x (br-r37-c1-prdir)

## Problem
Last session's weighted-COO fix (br-r37-c1-coowt) was UNDIRECTED-only. Directed
pagerank fell back to the nodelist adjacency_arrays (Python nodelist
canonicalisation + per-edge node string->index lookups): unweighted ~2.0-2.35x
slower, weighted ~2.65-3.58x slower than nx.

## Lever
1. adjacency_default_order_index_arrays + adjacency_default_order_arrays: add a
   GraphRef::Directed branch building the row-major out-adjacency COO
   (rows=source, cols=target, each edge ONCE) from successors_indices; weights
   read by index pair. New DiGraph::edges_indexed() iterates the index-keyed edge
   store directly so the WEIGHTED build does ONE attr lookup/edge (no per-edge
   edges.get(&(u,v)) hash).
2. _pagerank_scipy: route directed (and undirected) through the default-order
   builders for both the unweighted index path and the weighted path (dropped the
   not-is_directed gate). nodelist == list(G) so the index-ordered COO aligns;
   matrix assembly is order-independent.

## Proof
- DiGraph pagerank parity 0/50 (weighted+unweighted, exact <1e-12); to_scipy +
  adjacency_matrix directed (weighted+unweighted) byte-identical to nx 0/40;
  pytest pagerank/to_scipy/adjacency_matrix 519 passed.
- Native directed weighted COO build (6000 edges) 8.9->1.4ms. pagerank (min-of-15):
  unweighted n=500/1000 2.0x slower -> 0.66x/0.58x FASTER; weighted n=500/1000/2000
  3x slower -> 1.68x/1.92x/1.89x (improved; residual is wrapper edge-attr sync, not
  the COO).
