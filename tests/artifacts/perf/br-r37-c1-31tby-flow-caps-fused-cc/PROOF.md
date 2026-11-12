# br-r37-c1-31tby — fuse flow capacity validators into one edge scan

## Lever
The four high-level flow wrappers (`maximum_flow`, `maximum_flow_value`,
`minimum_cut`, `minimum_cut_value`) called `_flow_has_infinite_capacity`
(route-to-nx decision) then `_all_flow_caps_integral` (int-coercion flag)
back-to-back — TWO full `edges(data=True)` materializations
(`_native_edges_with_data`) per flow call. Fused into one pass
`_flow_caps_summary` returning `(needs_nx, all_int)`.

## Isomorphism / behavior parity
`_flow_caps_summary` reproduces both helpers' per-edge logic exactly
(missing cap defaults to +inf -> route to nx; finite non-neg float is never
Integral; numpy/Fraction via numbers.Real/Integral ABC). `all_int` is only
consumed when `needs_nx` is False (every cap present/finite/non-neg Real),
matching the original short-circuit ordering.

## Golden sha256 (max_flow value+dict, min_cut value+partition over
## int/float/mixed caps + all_node_cuts BA(40,55,70)) — MY EDITS == HEAD:
9c0e494e7d94067eb18007fd973207f045906d64409af68c03f54c19efdd4cf5

Pre-existing int-0 vs float-0.0 divergences (float-cap graphs, value 0):
identical 18/224 on HEAD baseline — NOT introduced here.

## Deterministic work reduction (cProfile, all_node_cuts BA(60), 8 iters)
| metric | HEAD | fused | ratio |
|---|---|---|---|
| total profiler time | 0.403s | 0.303s | 1.33x |
| total function calls | 1,167,289 | 841,249 | 0.72x |
| `_native_edges_with_data` calls | 528 | 264 | halved |
| `__next__` (edge iter) | 212,784 | 106,392 | halved |
| capacity-scan cumtime | 0.219s | 0.115s | halved |

Broad win: applies to every max_flow / max_flow_value / min_cut /
min_cut_value call and all consumers (node/edge connectivity, all_node_cuts).

## Tests
1546 passed (flow/cut/connectivity suite), 0 failures.
