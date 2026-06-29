# br-r37-c1-mgisol (CopperCliff): native undirected-MultiGraph has_eulerian_path / is_semieulerian

## Root cause
The `has_eulerian_path` wrapper called `_raw_has_eulerian_path(G)` for self-loop-free
undirected multigraphs. That binding built the FULL `gr.undirected()` simple-graph
projection (clones every node/edge attr + per-element ledger) AND crossed into Python
once per node for the degree view — ~1.44ms / **0.11x vs nx** at n=300. `is_semieulerian`
(= `has_eulerian_path and not is_eulerian`) inherited the tax -> 0.20x. (`is_eulerian`
was already fast: its wrapper uses the br-euldense Python fast path.)

## Fix (pure-Python, no Rust)
Mirror `is_eulerian`'s br-euldense pattern in the `has_eulerian_path` wrapper: for
self-loop-free multigraphs, nx's undirected test is just "<=2 odd-degree vertices AND
connected", so run it directly on the fast MultiGraph degree view + native
`is_connected` (which has its own fast multigraph path). Self-loop multigraphs still
delegate to nx (unchanged); simple graphs keep the native kernel; directed unchanged.

A native-binding variant (structure-only projection) was tried and REVERTED — it only
reached 0.31x because allocating the simple Graph + is_connected(&simple) is itself the
bottleneck; the Python path reusing the fast is_connected(MultiGraph) wrapper wins.

## Head-to-head (min of 8, undirected MultiGraph n=300, cycle + parallels)
| function          | before | after  |
|-------------------|--------|--------|
| has_eulerian_path | 0.11x  | 1.46x  |
| is_semieulerian   | 0.20x  | 1.53x  |
| is_eulerian       | 1.48x  | 1.48x (unchanged) |

## Parity
0 mismatches over 600 random multigraphs x3 predicates (parallels, +/- self-loops,
+/- isolates, error contracts) + empty/single-node edge cases. 603 euler conformance
tests pass.
