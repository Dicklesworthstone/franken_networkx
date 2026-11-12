# make_max_clique_graph — O(C^2) set-rebuild -> O(C) set materialize + bulk edges

## Lever
fnx's clique-intersection graph rebuilt `set(cliques[right_index])` INSIDE the
O(C^2) inner pair loop — O(C^2) set constructions instead of O(C) — and added
each L-edge with a separate PyO3 `add_edge` call. nx materializes each clique set
ONCE (`enumerate(set(c) for c in find_cliques(G))`) and bulk `add_edges_from`.
Mirrored nx: pre-build `clique_sets` once, comprehension over i<j pairs, single
`add_edges_from`. Only the unavoidable O(C^2) pairwise intersections remain.

## Correctness (byte-exact)
48 comparisons (gnp n=30..60, p=0.1..0.3, seeds 0..11): nodes 0..C-1 + edge
list identical to nx, 0 mismatches. Edge order (i,j) ascending == nx's
combinations(cliques,2). golden sha 706c89185a8bccea == nx. 246 clique/operator
tests pass.

## Benchmark (warm min, interleaved before/after) — ratio = nx/fnx
| graph         | BEFORE fnx        | AFTER fnx         | self-speedup |
|---------------|-------------------|-------------------|--------------|
| gnp(60,0.1)   | 2.256ms (0.53x)   | 1.081ms (1.11x)   | 2.09x        |
| gnp(80,0.12)  | 7.915ms (0.52x)   | 3.593ms (1.14x)   | 2.20x        |
| gnp(100,0.1)  | 15.202ms (0.50x)  | 6.890ms (1.10x)   | 2.21x        |

fnx flipped from ~2x SLOWER than nx to faster. ~2.2x self-speedup. Score>=2.0.
