# is_weighted — scan via to_dict_of_dicts kernel (sibling of is_negatively_weighted)

## Lever
is_weighted's whole-graph branch did `all(weight in data for _,_,data in
G.edges(data=True))` — paying the per-edge edges(data=True) materialization tax,
~2.2x slower than nx on WEIGHTED graphs (where `all` can't short-circuit and
walks every edge). Routed through the native to_dict_of_dicts kernel (overlay-safe
live edge dicts). Same lever as is_negatively_weighted (br-r37-c1-u45px).

## Correctness
30 cases (di/undirected x modes {all-weighted, one-missing, none, alt-attr} x
weight {weight,cost} x edge= form x post-creation del-attr mutation): 0 mismatches
vs nx, before AND after. golden 5a9240dd. 1119 weighted/predicate tests pass.

## Benchmark (warm min, interleaved before/after)
| graph             | BEFORE    | AFTER    | self-speedup |
|-------------------|-----------|----------|--------------|
| weighted BA(300)  | 0.4390ms  | 0.1120ms | 3.9x         |

Flips 0.46x slower -> 1.8x FASTER than nx.
