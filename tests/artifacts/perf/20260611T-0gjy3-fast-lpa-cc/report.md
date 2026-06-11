# br-r37-c1-0gjy3 — community.fast_label_propagation_communities

## Problem
Not overridden in `community.py` — the `from networkx... import *` re-export
ran nx's queue-driven LPA (Traag & Šubelj 2023) directly against the fnx
Graph. **~2-3x slower than nx** (grows with n) from per-node adjacency-view
rebuilds. Same root cause as `asyn_lpa_communities` (br-r37-c1-h4bad).

## Lever
De-delegate into an fnx-native in-process impl for the concrete simple
unweighted `Graph`. `seed` is already a real CPython `random.Random` (via
`py_random_state`), so the Python algorithm is byte-exact. Same three levers
as asyn_lpa (key-only `_native_adjacency_keys` snapshot + index-space loop +
reusable mark-array replacing nx's per-node `Counter`), plus one specific to
this algorithm:

- nx seeds the work queue with `seed.shuffle(deque(G))`. `deque[i]` is O(n),
  so shuffling a deque is **O(n^2)**. Shuffling a plain list of indices yields
  the **identical permutation** (Fisher-Yates draws depend only on `len`, not
  the container type or element values) in O(n), then seeds the work `deque`.
- The queue/membership-set (`nodes_set`) become a `deque` of ints + a `bool`
  array, so the hot enqueue/membership path is pure int.

Byte-exact: index labels are the same 0..n-1 ints nx uses; the mark-array's
`touched` list preserves first-seen label order so the tie set and every
`seed.choice` draw match; `groups` is rebuilt in node order.

Weighted / directed / multigraph / subgraph-view / non-fnx delegate to nx
(directed uses pred+succ + in_edges; weighted reads edge data — different
paths). Pure-Python change in `community.py`. No Rust change.

## Result (interleaved min-of-N, same host window)
| case          | before (nx-on-fnx) | after (native) | nx     | self-speedup | after vs nx |
|---------------|--------------------|----------------|--------|--------------|-------------|
| n400 p0.05    | 9.99 ms            | 2.94 ms        | 3.97   | 3.40x        | 0.74x (1.35x faster) |
| n800 p0.03    | 27.78 ms           | 7.06 ms        | 8.72   | 3.94x        | 0.81x (1.24x faster) |
| n1500 p0.02   | 67.08 ms           | 16.78 ms       | 19.67  | 4.00x        | 0.85x (1.17x faster) |

## Proof
- Golden sha256 over the order-sensitive community stream: **before == after
  == nx**, identical at all three sizes (`proof.json`).
- `proto_idxspace.py`: 650 cases (sizes/seeds + string-keyed + isolated
  nodes) vs nx — 0 fails.
- `verify_fnx_parity.py`: 435 fnx-vs-nx(converted) cases incl. isolated
  nodes + weighted-delegation — 0 fails.
- `tests/python/test_community_*`: 51 passed, 1 skipped.
