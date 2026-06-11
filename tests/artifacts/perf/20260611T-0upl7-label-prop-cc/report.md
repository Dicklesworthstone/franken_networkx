# br-r37-c1-0upl7 — community.label_propagation_communities

## Problem
The prior override (br-r37-c1-lpstruct) already avoided the full faithful
conversion by building a *structural* `nx.Graph` (nodes + edges) and running
nx's semi-synchronous LPA on it — but that still pays an `nx.Graph` build +
nx's pure-Python algorithm over nx adjacency views every call (~1.8x nx).

## Lever
Fully de-delegate for the simple `Graph`. The semi-synchronous algorithm only
needs (a) a proper graph colouring and (b) per-node neighbour-label
frequencies. Run it in index space over a one-time key-only adjacency
snapshot (`_native_adjacency_keys`) with a reusable mark-array, and obtain the
colouring from fnx's native `greedy_color` (verified byte-exact with nx's
default `largest_first` strategy). No `nx.Graph` build, no view access.

Byte-identical to nx:
- Colour classes are processed in nx's exact order — `greedy_color`'s
  dict-iteration order, mirroring nx's `_color_network`.
- Within a colour class the update order is irrelevant: a proper colouring
  makes each class an independent set, so same-class updates never see each
  other's labels.
- Labels are the same 0..n-1 ints; the Prec-Max tie-break (`max` of the
  most-frequent label set) and the final node-order grouping match.
- Directed graphs raise `NetworkXNotImplemented` (via delegation, as nx's
  `@not_implemented_for('directed')`); multigraph / view / non-fnx delegate.

Pure-Python change in `community.py`. No Rust change.

## Result (interleaved min-of-N, same host window; before = structural-nx-graph override)
| n    | before (ms) | after (ms) | nx (ms) | self-speedup | after vs nx |
|------|-------------|------------|---------|--------------|-------------|
| 300  | 4.68        | 1.66       | 3.50    | 2.81x        | 0.48x (2.1x faster) |
| 800  | 15.41       | 5.65       | 10.85   | 2.73x        | 0.52x (1.9x faster) |
| 1500 | 31.31       | 11.93      | 21.22   | 2.62x        | 0.56x (1.8x faster) |

## Proof
- Golden sha256 over the order-sensitive community stream: **before == after
  == nx**, identical at all three sizes (`proof.json`).
- `proto_idxspace.py`: 505 cases (sizes/seeds + string-keyed + isolated
  nodes) vs nx — 0 fails.
- `verify_fnx_parity.py`: 506 fnx-vs-nx(converted) cases incl. string-keyed,
  isolated nodes, and the directed `NetworkXNotImplemented` contract — 0 fails.
- `tests/python/test_community_*`: 51 passed, 1 skipped.
