# operators.*_all — route submodule to native fnx (4.5-8x vs old path)

## Problem
`operators.py`'s `union_all` / `intersection_all` / `compose_all` /
`disjoint_union_all` ran nx's pure-Python *_all on the fnx graphs (`_nx_all.X`)
then double-converted via `_from_nx_graph`, ignoring fnx's native top-level
implementations. Submodule path at 3-4 × 400-node graphs:

| function           | old submodule | fnx top-level | slowdown |
|--------------------|---------------|---------------|----------|
| union_all          | 23.8 ms       | 3.7 ms        | 6.4x     |
| disjoint_union_all | 26.5 ms       | 5.8 ms        | 4.5x     |
| compose_all        | 26.6 ms       | 3.3 ms        | 8.1x     |
| intersection_all   | 11.4 ms       | 1.8 ms        | 6.3x     |

## Lever
Route each `*_all` method (clean `operators.py`) to the fnx top-level native
impl, dropping the `_nx_all` call + `_from_nx_graph` double-conversion (and the
now-unused imports). Same pattern as the product routing. Returns fnx graph
type. No Rust change; contested `__init__.py` untouched.

## Result (routed vs genuine nx; ~4.5-8x vs the old submodule path)
| function           | routed (fnx) | genuine nx |
|--------------------|--------------|------------|
| union_all          | 3.69 ms      | 2.97 ms    |
| disjoint_union_all | 5.85 ms      | 6.30 ms    |
| compose_all        | 3.28 ms      | 3.27 ms    |
| intersection_all   | 1.80 ms      | 1.60 ms    |

## Proof
- Golden full signature (nodes+node-attrs + edges+edge-attrs, order-insensitive)
  vs genuine nx, attributed inputs, incl. `union_all(rename=...)`: all 5 cases
  **0 fails** over 30 trials each (`proof.json`).
- `tests/python -k "product or operator or union or compose or intersection or
  disjoint"`: 581 passed, 0 failed.
