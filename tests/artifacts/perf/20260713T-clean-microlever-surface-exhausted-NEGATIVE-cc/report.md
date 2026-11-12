# Clean one-turn micro-lever surface EXHAUSTED — NEGATIVE (cc, 2026-07-13)

Consolidation record after a long productive session. The clean, solo-safe, byte-identical,
one-turn perf-lever surface that the cc lane mines (String→int, alloc-for-count, self-loop index,
edges_ordered materialization) is now comprehensively worked. Every candidate a fresh grep surfaces
is DONE, a `_orig_*`/`_ab` A/B BASELINE (kept intentionally, not production), DEAD, non-deterministic,
or already index-native. Recorded so the next turn skips re-scanning these and goes to the frontier.

## Families COMPLETE this session (do not re-mine)

- **Self-loop index family** — `core_number` guard (corenumsl 1.67x), `nodes_with_selfloops`
  (selfloopidx 5.15x), `number_of_selfloops` (numselfidx 309x). All `has_edge(node,node)` /
  `edges_ordered().filter(left==right)` → `has_edge_by_indices(i,i)` / index count.
- **centrality_to_dict throwaway String** — in/out/total `degree_centrality` inlined (idcbind
  1.48x, tdcbind 1.59x). Remaining `centrality_to_dict` callers (betweenness/closeness/eigenvector/
  katz/pagerank/harmonic/load/percolation/clustering/square_clustering) are O(V·E)/iterative →
  dict-build Amdahl-diluted. The with-GIL binding A/B harness (`networkx_head_to_head_indeg_binding`)
  exists for future binding levers.
- **k-core family route-to-native** (k_core 20.3x, k_shell/crust/corona 5-8x); **is_isomorphic
  edge_count** (isoedgecount); **edge_boundary/cut-measure/conductance** (ebidx/cutexpidx).

## Remaining `neighbors(x).len()` / `edges_ordered()` scan hits are NOT live levers

Every hit a grep for `neighbors(x).unwrap_or_default().len()` / `edges_ordered().iter().filter/map`
turns up is in a `_orig_string` / `_orig_alloc` A/B BASELINE (the pre-lever version kept for the
paired A/B, e.g. `is_strongly_regular_orig_string`, `node_degree_xy_orig_alloc`,
`gutman_index_orig_string`, `bfs_beam_edges_orig_alloc`) — the PRODUCTION twins are already
index-native (srmark etc.). `connected_dominating_set`'s `max_by_key(neighbors().len())` is a
single one-time start pick in a NON-DETERMINISTIC function (HashSet iteration). The dead graphml
`edges_ordered().len()` capacity sites remain dead.

## DEAD kernels catalogued this session (reachability rule / package-vs-module `_fnx` trap)

`double_edge_swap_seeded` + `directed_edge_swap_seeded` (REVERTED c3788a42a — public
double/directed_edge_swap reimplement in pure Python for nx RNG-order parity; `swap.py`
`import franken_networkx as _fnx` → `_fnx.double_edge_swap` is the PACKAGE fn, not the
`double_edge_swap_rust` binding); plus the earlier clique/coloring approx kernels, product/line_graph
plain kernels, greedy_color non-largest_first, write_graphml_string_*, number_of_selfloops_rust.
See [[pyo3_wrapper_can_itself_be_dead]] — the reachability trace (resolve `_fnx`, READ the `.py`
body, watch for `import random`/`*_fast` siblings) is MANDATORY before any kernel A/B.

## Frontier (NOT a clean one-turn solo increment)

1. MultiGraph integer-adjacency epoch ([[thp6w6_multigraph_intadj_epoch]]) — the only live
   head-to-head LOSSES (mg_selfloop ~0.26x, mdg_out_edges ~0.39x). Multi-slice, slice-1 regressed,
   needs peer coordination (MagentaTrout/cod active on adjacent MultiGraph work — 4c9d2680c
   connected_components, 4a4188afb number_of_isolates).
2. Binding-layer constant factors behind the with-GIL harness — remaining candidates floor-dominated.

Net: the next productive work is architectural (MultiGraph epoch) or coordinated, not another
grep-and-swap micro-lever. Verify `.py` reachability FIRST for any kernel candidate.
