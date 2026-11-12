# contracted_nodes / identified_nodes — copy + local remap (mirror nx)

## Lever
identified_nodes rebuilt the ENTIRE result graph node-by-node and edge-by-edge
(O(N+E) per-PyO3 add_node/add_edge), even though contracting v into u only
touches v's O(deg(v)) incident edges. Replaced with nx's own algorithm: H =
G.copy() (fast native copy, preserves node/edge order + graph attrs), remove v,
remap only v's incident edges to u, record contraction bookkeeping. O(deg(v))
edge ops + one native copy instead of a full Python rebuild.

## Correctness (byte-exact vs nx)
320 contractions across simple/directed/weighted/multi/multidi graphs x
self_loops {True,False}: node+edge+graph-attr signature identical to nx, 0
mismatches. golden sha dad5073513794d08. Verified: copy=False returns caller's
graph (result is G) matching nx; v-not-in-G NetworkXError contract; graph-level
attrs preserved; node/edge "contraction" dicts match nx docstring examples;
contracted_edge intact. 1216 contraction/minor/quotient tests pass.

## Benchmark (warm min, interleaved before/after) — ratio = nx/fnx
| graph      | BEFORE fnx        | AFTER fnx        | self-speedup |
|------------|-------------------|------------------|--------------|
| BA(300,4)  | 2.850ms (0.46x)   | 0.369ms (3.58x)  | 7.7x         |
| BA(800,5)  | 12.334ms (0.36x)  | 1.265ms (3.57x)  | 9.7x         |
| BA(1500,4) | 18.813ms (0.37x)  | 1.637ms (4.30x)  | 11.5x        |

fnx flipped from ~2.7x SLOWER than nx to 3.6-4.3x FASTER; self-speedup grows
with graph size (old rebuild was O(N+E), new is O(deg(v)) + native copy).
