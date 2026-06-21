# Correctness + perf WIN — gnm_random_graph complete-case parity (br-r37-c1-gnmcomplete)
# + REVERTED MultiGraph reorder regression (br-r37-c1-predrebuild NOTE)

- Agent: `BlackThrush` · 2026-06-21 · Files: `__init__.py`, `crates/fnx-classes/src/lib.rs`

## gnm_random_graph complete-case (WIN: correctness + perf)
Found while verifying the copy-walk reorder fixes: fnx.gnm_random_graph diverged from nx
in 11/500 random cases — ALL of them the COMPLETE case (m = n(n-1)/2). nx returns
`complete_graph(n)` (combinations(range(n),2) order) when m saturates, BEFORE drawing
RNG; the fnx Python wrapper instead did `m = min(m, max_edges)` then REJECTION-SAMPLED
all edges, yielding the sampling order (and rejecting ~every later draw). Added nx's
`if m >= max_edges: return complete_graph` short-circuit (combinations order).
- Parity: 3000 random (n,m incl m>=max) byte-exact edge order + adjacency + nodes +
  graph attrs (was ~2.2% divergent on the complete subset). pytest -k
  'gnm or gnp or random_graph' 1364 passed.
- Perf (bonus): gnm(complete) nx/fnx 2.52x @n=100, 1.83x @n=300 — the saturated
  rejection loop (reject ~every draw) is replaced by a direct batched complete build.

## REVERTED: MultiGraph reorder rebuild (regression)
Tried the O(E)-rebuild lever (that won 10x on the undirected integer Graph reorder and
helped the directed MultiDiGraph 18%) on the undirected MultiGraph String reorder
(lib.rs reorder_rows_for_nx_copy_walk). It REGRESSED dense MultiGraph.copy() 0.60x ->
0.44x: the undirected early/late split needs pos(u) AND pos(v), so the rebuild does 2
adjacency passes + 2 get_index_of/edge, outweighing the cheap integer-keyed sort it
removed (unlike the directed 1-pass succ-walk with no lookups). Reverted to the
sort-based form; left an in-code NOTE so it is not re-attempted.
