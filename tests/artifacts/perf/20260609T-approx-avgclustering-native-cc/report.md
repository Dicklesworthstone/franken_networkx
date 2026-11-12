# perf(approximation.average_clustering): native bulk-adjacency sampler

br-r37-c1-2poe6

## Problem
`fnx.approximation.average_clustering` went through the generic
_ApproximationNamespace __getattr__: convert fnx->nx then run nx's Schank-Wagner
trials loop, whose per-trial `list(G[node])` + `u in G[v]` execute on slow fnx
adjacency. ~3x slower than nx (n=500 tr=1000: nx 1.9ms vs fnx 6.3ms).

## Lever (one)
Concrete native method: snapshot adjacency once via the bulk native
`G.adjacency()` (order-preserving lists + sets), then run nx's EXACT sampler on
local dicts — all `int(seed.random()*n)` indices generated first, then per-trial
`seed.sample(nbrs, 2)` + membership. Identical RNG call sequence + neighbor
order => byte-identical to the previous fnx result.

Touched: python/franken_networkx/__init__.py (_ApproximationNamespace.
average_clustering + __doc__ mirror for introspection parity).

## Proof (behavior-preserving)
Native sampler == previous fnx result over 60 cases (BA n=40..300, varied
trials/seed), 0 mismatches. Directed raises NetworkXNotImplemented; seeded calls
deterministic. pytest -k "clustering or approxim": 585 passed.
AVGCLUST_SHA dba4e53c419bab7ef8f6828b50d9bbf537fd2690cf519c0391dcf690890f588c

## Timing (warm min-of-8, BA m=4, trials=1000)
| N    | nx     | fnx before | fnx after |
|------|-------:|-----------:|----------:|
| 500  | 1.90ms |   6.29ms   |  1.95ms (parity, 3.2x self) |
| 1000 | 2.01ms |  12.01ms   |  3.21ms (1.6x slower, 3.7x self) |
| 2000 | 4.30ms |  25.01ms   |  8.16ms (1.9x slower, 3.1x self) |

~3x self-speedup; parity with nx at common sizes. Residual at large-N-small-
trials = the O(V+E) adjacency snapshot (nx samples adjacency lazily); a
trials-vs-V gated lazy path could close it (noted for follow-up).

## Score
Impact: moderate-high (3x self-speedup, 3x slower -> parity at common sizes).
Confidence: high (0/60 behavior-preserving, 585 tests). Effort: low. Score >= 2.0.
