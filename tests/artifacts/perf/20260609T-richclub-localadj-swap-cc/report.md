# perf(rich_club_coefficient normalized): local-adjacency double-edge swaps

br-r37-c1-richclubswap

## Problem
`rich_club_coefficient(G)` (default normalized=True) normalizes against a
randomized reference built by Q*m double-edge swaps. The swap loop mutated the
fnx GRAPH per attempt: `list(G[u])`/`list(G[x])` adjacency views, `x in G[u]`
membership, and 4 `add/remove_edge` — many PyO3 round-trips × ~Q*m attempts.
~4x SLOWER than nx (N=400 Q=100: nx 933ms vs fnx 3755ms).

## Lever (one)
Run nx's IDENTICAL double_edge_swap loop on a LOCAL ordered-dict adjacency
snapshot (`{n: dict.fromkeys(G[n])}`). dict.fromkeys preserves `G[u]` iteration
order, so `rng.choice` picks the same neighbors and the swap sequence — hence
the randomized graph — is byte-identical for a given seed. Rich-club is then
computed straight from the final adjacency (`_rich_club_rc_from_adjacency`,
same formula/order as the kernel). No per-swap PyO3.

Touched: python/franken_networkx/__init__.py (rich_club_coefficient +
_rich_club_randomized_coefficients + _rich_club_rc_from_adjacency).

## Proof (nx-exact)
- vs GENUINE nx (orig_func): 36 cases (BA n=60..180, varied Q/seed) 0 mismatches
  (4 cases skipped where nx itself ZeroDivisionErrors on a 0-rc degree class).
- Earlier: current fnx == nx bit-exact (seeds 42/7/123); new == current fnx over
  24 cases (8 seeds x 3 sizes) — so new == nx.
- normalized=False core unchanged; error contracts (<4 nodes, <2 edges, swaps>
  tries, max_tries) preserved. pytest -k rich_club: 61 passed.
RICHCLUB_SHA 6452e41392cee1a489ab017463d8140a4cee5b0cc714a5ada033f11ee469dfdd

## Timing (warm min-of-3, BA m=4, Q=100)
| N   | nx (genuine) | fnx before | fnx after | before vs nx | after vs nx | self |
|-----|-------------:|-----------:|----------:|-------------:|------------:|-----:|
| 400 |     933ms    |   3755ms   |   351ms   |   ~4x slower |  0.38x (2.6x faster) | 10.5x |
| 600 |    1458ms    |   7899ms   |   564ms   |   ~5x slower |  0.39x (2.6x faster) | 14x  |

## Score
Impact: high (~4x slower -> 2.6x faster vs nx; 10-14x self-speedup). Confidence:
high (0/36 vs nx + 0/24 vs current-fnx, 61 tests). Effort: moderate. Score >> 2.0.
