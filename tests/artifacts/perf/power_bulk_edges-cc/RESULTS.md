# power(G,k) — bulk add_nodes_from/add_edges_from in the power_rust rebuild

## Lever
The integer-k branch ran power_rust (native) then rebuilt the result via a
per-edge add_node/add_edge loop — 98460 add_edge PyO3 calls on BA(150,3)^3, more
costly than the native kernel itself (0.16s rebuild vs 0.12s kernel). Switched to
bulk add_nodes_from / add_edges_from over the same generators.

## Isomorphism (byte-identical to PRIOR fnx output)
add_edges_from iterates the generator in the same order as the old sequential
loop, so node/edge insertion order is unchanged. BEFORE-fnx and AFTER-fnx edge
list sha are IDENTICAL: b34829fbda57b61f (== proof of behavior preservation).
78 power tests pass.

NOTE: fnx.power's edge ITERATION order already differed from nx (power_rust
rebuild order vs nx's per-node BFS) — same edge SET (9846 == 9846) and same node
order, a PRE-EXISTING non-semantic difference, unchanged by this commit. The
order-sensitive "54 mismatches vs nx" in the prove script is that pre-existing
divergence, NOT a regression (BEFORE-fnx has the identical sha).

## Benchmark (warm min, interleaved before/after) — ratio = nx/fnx
| graph         | BEFORE fnx       | AFTER fnx        | self-speedup |
|---------------|------------------|------------------|--------------|
| BA(150,3)^3   | 36.69ms (0.90x)  | 20.62ms (1.57x)  | 1.78x        |
| BA(250,4)^2   | 40.76ms (1.07x)  | 21.78ms (1.94x)  | 1.87x        |
| BA(150,3)^4   | 44.61ms (0.83x)  | 24.98ms (1.47x)  | 1.79x        |

fnx flipped from slower-than-nx to 1.47-1.94x faster. ~1.8x self-speedup.
