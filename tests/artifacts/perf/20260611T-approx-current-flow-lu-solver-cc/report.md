# perf: approximate_current_flow_betweenness — sparse LU solver instead of dense O(n^3) inverse

Bead: br-r37-c1-wz3sy. nx's default solver="full" precomputes a DENSE O(n^3) inverse
Laplacian (np.linalg.inv) even though the approximation only does k=O(log n / epsilon^2)
solves of L p = b. The sparse "lu" solver (one scipy LU factorization + a cheap
back-substitution per sample) computes the IDENTICAL p (both exactly solve L p = b).

## Lever (ONE)
Substitute solver="lu" for the "full" default in the delegation. Verified identical:
max |full - lu| ~ 1e-16 (machine epsilon) over the corpus; nx itself confirms full vs lu
match to 1.5e-16. An explicit solver= choice (lu / cg) is honoured as given.

## Proof (machine-exact)
- Golden: fnx-new(lu default) == fnx-old(full) within machine epsilon (worst 4.4e-16)
  over 9 graphs x seeds {1,7,42}: 74ce86ca48730ab342b101c91e2068e803aa69543f44855bdcfe96532623867b
- 8 approximate_current_flow conformance tests pass; 1182 centrality tests pass.

## Benchmark (connected_watts_strogatz, min-of-4, seed=1)
| n   | nx default (full) | fnx (lu) | ratio       |
|-----|-------------------|----------|-------------|
| 200 | 213 ms            | 36.1 ms  | 0.17x (5.9x FASTER) |
| 400 | 399 ms            | 82.4 ms  | 0.21x (4.8x FASTER) |

nx default 4.8-5.9x slower -> fnx FASTER, result identical to machine epsilon. The dense
O(n^3) inverse was the bottleneck; sparse LU (factor once + k back-subs) replaces it.

## NOTE (separate pre-existing bug, filed)
fnx's delegated approximate already diverges from nx by ~0.05-0.09 on some graphs (n=30,80)
because the fnx->nx conversion's adjacency order (and thus its RCM ordering) differs from
nx's original — fnx_old(full) vs nx maxdiff 0.05-0.09, RCM(conv)!=RCM(orig). This lu change
is orthogonal (preserves fnx's exact output, machine eps) and does NOT affect that. Filed
separately.
