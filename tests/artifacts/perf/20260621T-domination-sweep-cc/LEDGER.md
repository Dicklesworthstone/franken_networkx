# VERIFICATION — comprehensive domination sweep (4 fresh domains, ~50 fns); residuals are all BOUNDED

- Agent: `BlackThrush` · 2026-06-21 · MEASURED (warm min-of-N, taskset, PYTHONHASHSEED=0)

## Swept this session, all WIN/parity vs nx (representative ratios)
- hashing/cycles/coloring/chordal/linkpred: minimum_cycle_basis 9.75x, degree_assortativity 46x,
  square_clustering 24x, average_neighbor_degree 13.7x, greedy_color 10.5x, is_chordal 5.5x,
  chordal_graph_cliques 4.3x, cycle_basis 3.1x, find_cycle 8.3x, jaccard 2.3x, adamic_adar 2.2x,
  triangles 6.2x, all_pairs_LCA 1.9x, wl_hash ~1.0x.
- serialization/IO: node_link_data 1.40x, node_link_graph roundtrip 1.42x, to_dict_of_lists 2.07x,
  cytoscape_data 1.09x, generate_edgelist 1.16x, generate_adjlist 1.07x.
- multigraph algos: MG edges(data) 4.66x, MDG scc 3.70x, MG to_undirected 1.61x, MDG in_degree 2.36x,
  MG number_of_selfloops 3.16x, MG degree 1.22x, MDG pagerank 1.15x, MG number_of_edges 562x.
- community/clique/bipartite: node_redundancy 805x, greedy_modularity 23x, louvain 12.8x,
  bipartite.spectral_bipartivity 5.3x, label_propagation 2.69x, bipartite.clustering 2.24x,
  is_bipartite 8.5x, modularity 1.48x, find_cliques 1.06x.

## The 4 residuals — all BOUNDED, none a clean MY-file win
1. adjacency_data 0.76x (grows to 0.68x@n=2000): native kernel `adjacency_data_simple` in
   `readwrite.rs` (a PEER's actively-modified file) does `edge_dict = d.copy(); set_item(id)` per
   neighbor (2*E PyDicts) vs nx's single `{**d, id: nbr}` comprehension. node_link_data WINS 1.40x,
   so the kernel CAN win — the fix is to build the dict directly (kernel-side, peer-owned). In-process
   Python comprehension is 0.29x (per-access tax), so NOT a Python-side fix. -> peer opportunity.
2. asyn_fluidc 0.78x: DELEGATED to nx (randomized + set/dict-order dependent) -> must stay delegated
   for parity; 0.78x is the fnx->nx conversion-tax floor (same class as steiner_tree, max_weight_matching).
3. MG connected_components 0.63x@n=300 -> 1.03x@n=3000: a tiny per-call constant overhead (multigraph
   String-keyed substrate), amortizes to parity-win at scale. Not worth a targeted fix.
4. max_weight_matching/min_edge_cover 0.81x: conversion-tax + order-sensitive (documented 28129ef1c).

## Conclusion
Non-substrate, non-peer surface is DOMINATED. Remaining sub-1x cases are: PEER-owned native kernels
(adjacency_data), randomized/order-sensitive DELEGATED fns (asyn_fluidc, steiner, max_weight_matching),
and the multigraph String-keyed construction substrate (bead yl606). No clean BlackThrush-file lever
left in these domains.
