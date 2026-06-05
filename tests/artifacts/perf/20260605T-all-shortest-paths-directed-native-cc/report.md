# perf: all_shortest_paths directed unweighted native — nx-order kernel, drop delegation

Bead br-r37-c1-wjz3x (extends br-r37-c1-qiplw, which fixed the undirected case in
87a595094).

## Lever
After 87a595094, undirected unweighted `all_shortest_paths` ran natively but
DIRECTED unweighted still delegated to networkx. The reason: the
`all_shortest_paths_directed` kernel still ended with `paths.sort()` (lexicographic
String sort — e.g. "10" < "4"), which does not match nx's iteration order. (The
prior commit's `replace_all` only matched the undirected enumeration block; the
directed block lacked one comment line and was skipped.)

The directed kernel's forward BFS already builds predecessor lists in nx's
BFS-discovery order — only the final `paths.sort()` was wrong. Replace it with
nx's exact predecessor-DAG DFS (`_build_paths_from_predecessors`: stack walk from
target back to source with a `seen` set). Then drop the `not G.is_directed()`
guard in the wrapper so directed unweighted also routes to `_raw_all_shortest_paths`.

## Correctness
- Raw directed kernel vs nx (`directed_raw_kernel_proof.py`): 150 random digraphs,
  all pairs in [0,6): 4484 cases, 0 mismatches on full path-list order.
- Full wrapper differential (`parity_proof.py`, directed + undirected + karate):
  3651 path-cases + 705 no-path/error cases, 0 mismatches on path order AND error
  class+message. golden_sha256 unchanged:
  263581cb6c040af95ac009ae2c561fc0207b0d4cc627d8cd6038d7cee4b3885b.
- 515 shortest-path pytest pass; fnx-algorithms kernel tests pass.

## Perf (warm min-of-12, single pair, directed gnp)
- n=1000: OLD 15.25x -> NEW 0.29x  (self 11.107ms -> 0.210ms = 53x; ~3.4x faster than nx)
- n=3000: OLD 17.89x -> NEW 0.11x  (self 41.795ms -> 0.265ms = 158x; ~9x faster than nx)

all_shortest_paths is now fully native for the unweighted case (both directions);
the full fnx->nx per-call conversion is eliminated.
