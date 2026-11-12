# Negative-Evidence Ledger — MultiDiGraph condensation (br-r37-c1-condmdg)

- Agent: `BlackThrush` · 2026-06-20 · Base origin/main `a9f239c75`
- File touched: `crates/fnx-python/src/algorithms.rs` (binding only)

## Root cause

`condensation(MultiDiGraph)` called `gr.digraph()`, which for a MultiDiGraph
builds a simple DiGraph via `multidigraph_to_simple_digraph` — cloning every
edge AttrMap, collapsing parallels with per-edge `has_edge`, rebuilding String
IndexMaps. SCC and the cross-SCC edge set are multiplicity-invariant, so the
whole projection is wasted: `0.15–0.18×` nx across all densities.

## Lever

Build the condensation directly on the multidigraph's distinct-successor index
adjacency + the native nx-ordered multidigraph SCC kernel
(`multidigraph_strongly_connected_components_nx_ordered`). Factored the assembly
into `build_condensation_py` shared by the simple-DiGraph and direct-MultiDiGraph
paths. The `(cu, cv)` first-seen dedup over distinct successors matches nx's
`for u, v in G.edges()` (parallel edges add no new SCC-pairs), so node labels,
members sets, edge SET + ITERATION ORDER, and `graph['mapping']` are byte-exact.

## Win / loss / neutral vs NetworkX 3.6.1 (warm min-of-N)

| n / m | #scc | OLD (conv) | NEW | NEW vs nx | self-speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1500 / 6000 | 51 | 0.17x | 3.47ms | **1.17x** | 7.1x |
| 2500 / 10000 | 97 | 0.17x | 11.25ms | 0.61x | 3.8x |
| 4000 / 16000 | 183 | 0.18x | 22.15ms | 0.52x | 3.4x |
| 4000 / 4000 | 3404 | 0.34x | 9.16ms | 0.99x | 3.1x |
| 4000 / 40000 | 1 | 0.15x | 44.46ms | 0.64x | 4.2x |

**Accounting: WIN at the documented density (n=1500, 0.15x→1.17x) and sparse
(0.99x); high-density still trails nx (0.52–0.64x) but is a 3.4–4.2× improvement
over the old path — a strict improvement everywhere, no regression.** DiGraph
path non-regressed (1.21x; refactor is behavior-preserving).

## Parity

2000 random MultiDiGraphs incl. parallel edges + self-loops: 0 mismatches over
node labels, members sets, edge set + iteration order, and `graph['mapping']`.
`pytest -k 'condensation or strongly_connected or scc'`: 780 passed.

## Next route

High-density residual is the DOUBLE successor-adjacency build (this branch's
`succ_adj` + the SCC kernel's own internal `successors`/`predecessors` Vecs,
~5× O(V+E) traversals total). A fused condensation kernel that builds the index
adjacency ONCE and returns both the SCC partition and `scc_of` would likely tip
the dense case to a win too. nx's giant-SCC fast case (one DFS + an edge scan)
is the bar to beat.
