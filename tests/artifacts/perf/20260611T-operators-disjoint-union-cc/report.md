# operators.disjoint_union — route submodule to native fnx (6x + return-type fix)

## Problem
`franken_networkx/operators.py` overrides the *product* and `*_all` operators
(returning fnx graph types) but left the binary operators as the
`from networkx.algorithms.operators import *` re-export. Most of those
(`union`/`compose`/`difference`/`symmetric_difference`/`intersection`) happen to
return fnx graphs because nx builds the result via `G.__class__()` — but
**`disjoint_union`** relabels through `convert_node_labels_to_integers` and
returns a plain **`nx.Graph`** (a drop-in type bug: every other operator here
returns an fnx graph) and runs ~6x slower than the native `fnx.disjoint_union`
(23 ms vs 3.8 ms on the submodule path at n=1600).

## Lever
Add a concrete `disjoint_union` to `operators.py` (clean / uncontested) that
routes to the fnx top-level `fnx.disjoint_union` — the native implementation
that returns the correct fnx graph type and is 2.5x faster than genuine nx.
Mirrors the existing product-wrapper pattern in the same file. No Rust change;
the contested, mid-refactor `__init__.py` is untouched.

## Result
- **Return type:** `nx.Graph` → `franken_networkx.Graph` (drop-in bug fixed).
- **Speedup:** ~6x vs the previous submodule path (23 ms → 3.97 ms at n=1600);
  2.51x (n=800) / 2.54x (n=1600) vs **genuine nx**.

| n    | routed (fnx) | genuine nx | speedup vs nx |
|------|--------------|------------|---------------|
| 800  | 3.97 ms      | 9.97 ms    | 2.51x         |
| 1600 | 8.68 ms      | 22.07 ms   | 2.54x         |

## Proof
- `operators.disjoint_union` returns `franken_networkx.Graph`.
- Golden node/edge-signature parity vs genuine nx: 80 graph-pairs, **0 fails**.
- `tests/python -k "disjoint_union or operator"`: 272 passed, 0 failed.

## Note
This was found while scouting the operator family (the only binary op with both
a perf gap and a type bug). The bigger open targets — `approximate_current_flow`
(br-r37-c1-wz3sy, ~12x via native Laplacian-inverse) and `large_clique_size`
(~2x de-delegation) — both live in the heavily-contested, mid-refactor
`__init__.py` and are deferred until it settles.
