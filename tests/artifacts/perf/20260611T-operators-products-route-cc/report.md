# operators.* products — route submodule to native fnx kernels (17-31x)

## Problem
`franken_networkx/operators.py`'s product wrappers
(`cartesian_product`/`tensor_product`/`lexicographic_product`/`strong_product`/
`modular_product`/`rooted_product`/`corona_product`/`power`) ran nx's
pure-Python product on the fnx graph (`_nx_product.X(G, H)`) **then** converted
the whole result back with `_from_nx_graph` — a slow path that ignored fnx's
native product kernels (`graph_product_fast`). Measured on the submodule path
(`fnx.algorithms.operators.X`) at |G|=80, |H|=60:

| function              | old submodule | fnx top-level (native) | slowdown |
|-----------------------|---------------|------------------------|----------|
| cartesian_product     | 253 ms        | 10 ms                  | 24.6x    |
| tensor_product        | 783 ms        | 25 ms                  | 31.0x    |
| lexicographic_product | 8019 ms       | 450 ms                 | 17.8x    |
| strong_product        | 1015 ms       | 34 ms                  | 29.6x    |

## Lever
Route each product method in the clean `operators.py` to the fnx top-level
native kernel (`_fnx.cartesian_product` etc.), dropping the `_nx_product` call
and the `_from_nx_graph` double-conversion. Same pattern as the shipped
`operators.disjoint_union` routing. No Rust change; the contested mid-refactor
`__init__.py` is untouched.

## Result (vs genuine nx, at |G|=80,|H|=60)
| function              | routed (fnx) | genuine nx | speedup vs nx |
|-----------------------|--------------|------------|---------------|
| cartesian_product     | 9.96 ms      | 31.81 ms   | 3.19x         |
| tensor_product        | 29.12 ms     | 136.25 ms  | 4.68x         |
| strong_product        | 43.51 ms     | 172.54 ms  | 3.97x         |
| lexicographic_product | 481.56 ms    | 917.41 ms  | 1.91x         |

Return type stays `franken_networkx.Graph`. ~17-31x faster than the previous
submodule path.

## Proof
- Golden full signature (nodes+node-attrs + edges+edge-attrs, order-insensitive)
  vs genuine nx over attributed inputs: all 8 products **0 fails** (`proof.json`).
- `tests/python -k "product or operator or corona or rooted"`: 411 passed, 0
  failed.

## Note
The bigger open targets (`approximate_current_flow` br-r37-c1-wz3sy ~12x,
`large_clique_size` br-r37-c1-eg2bz ~2x) remain blocked on the mid-massive-
refactor `__init__.py` (still `MM`). This win, like disjoint_union, was found by
scouting the clean `operators.py` submodule.
