# voronoi_cells — skip discarded-distance int-coercion (vs-nx gap closure)

## Lever
`voronoi_cells` only needs the SOURCE each node was reached from (`path[0]`),
never the distances. The general `multi_source_dijkstra_path` wrapper it called
int-coerces the full distance dict (`_sp_coerce_dist_to_int` /
`_sp_propagate_int_types`, ~10% of runtime) and rebuilds both dist+path dicts in
distance order — all discarded by voronoi. New `_voronoi_nearest_centers` runs
the raw kernel once, reorders only the nearest-center map, and skips the
int-coercion. Weighted/callable-weight inputs fall back to the exact wrapper.

## Correctness (byte-exact)
48 (centers) comparisons across ba/gnp/path/disconnected/weighted graphs vs
networkx: 0 mismatches (cell dict-key order + cell contents). Output order is
provably unchanged: the full wrapper also reorders via the no-G
`_reorder_by_distance` (stable sort by numeric distance); int-vs-float of equal
value sort identically, so skipping int-coercion cannot change order.
golden sha (BA600 centers {0,100,300}) = c49d5fadc62e3883...
pytest -k voronoi: 31 passed.

## Benchmark (warm min, interleaved before/after) — ratio = nx/fnx
| n    | k  | BEFORE fnx     | AFTER fnx      |
|------|----|----------------|----------------|
| 600  | 3  | 1.037ms (0.98x slower) | 0.969ms (1.11x FASTER) |
| 2000 | 5  | 3.864ms (0.97x slower) | 3.574ms (1.07x FASTER) |
| 5000 | 10 | 11.25ms (0.93x slower) | 10.86ms (1.02x FASTER) |
| 2000 | 50 | 3.897ms (0.97x slower) | 3.611ms (1.07x FASTER) |

fnx was consistently SLOWER than nx (a real vs-upstream gap); now consistently
faster. ~7% self-speedup, byte-exact. Gap-closure per the No-Gaps directive.
