# perf: is_k_edge_connected(k<=2) — nx's smart early-exits instead of native edge_connectivity

Bead: br-r37-c1-6hvhl. is_k_edge_connected with INTEGER k routed to the native
_raw_is_k_edge_connected binding, which computes a full edge_connectivity max-flow even
for k<=2 — 9.6x (n=400) to 19.2x (n=1000) SLOWER than nx. nx uses smart early-exits:
k==1 is plain connectivity, k==2 is connectivity with no bridge, only k>=3 needs the
flow-based edge_connectivity. (The non-int-k path already had nx's logic; the int path
didn't.)

## Lever (ONE)
Route every k through nx's exact algorithm over fnx's fast native primitives:
  if n < k+1: False
  if any degree < k: False
  k==1 -> is_connected; k==2 -> is_connected and not has_bridges; else edge_connectivity>=k
Byte-identical bool to both nx and the old native binding.

## Proof (byte-exact)
- Golden bool over 67 graphs (gnm random, complete, cycle, path, petersen, icosahedral,
  empty, star) x k in {1,2,3,4,5} == nx for every case:
  a486c8b401a92e2a37a68306e4e06d1925f9b85fa405028e4dd58d89417d925c
- Separately: 800-trial corpus (k=1..4) nx == old-native == new, 0 failures. Error
  contract (k<1 -> ValueError) preserved. 488 k_edge/connectivity tests pass.

## Benchmark (connected_watts_strogatz, min-of-8)
| case      | nx (ms) | fnx before (native) | fnx after | before vs nx | after vs nx |
|-----------|---------|---------------------|-----------|--------------|-------------|
| n400 k=2  | 4.90    | 44.2 (9.6x)         | 0.070     | 9.6x slower  | 70x FASTER  |
| n1000 k=2 | 14.2    | 285 (19.2x)         | 0.164     | 19.2x slower | 87x FASTER  |
| n400 k=3  | 59.1    | 43.5                | 43.3      | 0.74x        | 0.73x       |
| n1000 k=3 | 324     | 279                 | 301       | 0.86x        | 0.93x       |

k<=2: 9.6-19.2x slower -> 70-87x FASTER. k>=3: parity-or-faster (native edge_connectivity).
Byte-exact, pure-Python.
