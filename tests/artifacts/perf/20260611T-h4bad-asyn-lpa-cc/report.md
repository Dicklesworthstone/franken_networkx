# br-r37-c1-h4bad — community.asyn_lpa_communities

## Problem
`fnx.community.asyn_lpa_communities` was not overridden — the module's
`from networkx.algorithms.community import *` re-exported nx's pure-Python
LPA, which ran directly against the fnx Graph. **2.4–2.9x slower than nx**
(grows with n) because nx's loop rebuilds an adjacency view (`G[node]`) for
every node on every round, and each `G[node]` on an fnx graph is a PyO3
view construction.

## Key insight
nx's `seed` is already a real CPython `random.Random` (via
`py_random_state`), so the algorithm can stay in Python and remain
byte-exact — no native RNG needed.

## Levers (one structural change, three reinforcing parts)
De-delegate into an fnx-native in-process implementation for the concrete
simple `Graph`:
1. **One-time adjacency snapshot** via the key-only native crossing
   `G._native_adjacency_keys()` (unweighted, ~4x cheaper than the
   attr-bearing crossing) / `fnx_to_nx_adjacency` (weighted) — replaces the
   `O(rounds·V)` view rebuild.
2. **Index-space loop**: labels, the shuffle permutation and neighbour lists
   are plain `int`s (node → 0..n-1). Byte-exact because Fisher-Yates
   `shuffle` draws depend only on `len`, nx's labels are themselves the same
   0..n-1 ints, and the final `groups` mapping is rebuilt in node order.
3. **Reusable mark-array** replaces nx's per-node `Counter` /
   `defaultdict` (cProfile: Counter construction + its ABC instancecheck was
   ~half the runtime). `freq[label]` is a list index (no hashing); a
   `touched` list preserves first-seen label order so the best-label tie set
   — and thus every `seed.choice` draw — is identical to nx.

Directed / multigraph / subgraph-view / non-fnx graphs delegate to nx
(asyn_lpa supports directed, unlike `label_propagation_communities`).

Pure-Python change in `python/franken_networkx/community.py`. No Rust change.

## Result (interleaved min-of-N, same host window)
| case          | before (nx-on-fnx) | after (native) | nx     | self-speedup | after vs nx |
|---------------|--------------------|----------------|--------|--------------|-------------|
| n400 p0.05    | 12.05 ms (2.37x)   | 3.88 ms        | 5.08   | 3.11x        | 0.76x (1.3x faster) |
| n800 p0.03    | 29.92 ms (2.64x)   | 9.58 ms        | 11.33  | 3.12x        | 0.85x (1.2x faster) |
| n1500 p0.02   | 70.66 ms (2.92x)   | 22.53 ms       | 24.17  | 3.14x        | 0.93x (1.1x faster) |

## Proof
- Golden sha256 over the order-sensitive community stream: **before == after
  == nx**, identical at all three sizes (`proof.json`).
- `proto_markarray.py`: 665 cases (sizes/seeds + weighted + string-keyed)
  vs nx — 0 fails.
- `verify_fnx_parity.py`: 370 fnx-vs-nx(converted) cases incl. weighted,
  string-keyed, directed-delegation — 0 fails.
- `tests/python/test_community_*`: 51 passed, 1 skipped (incl. the
  no-fallback monkeypatch test + weighted-directed delegation test).
