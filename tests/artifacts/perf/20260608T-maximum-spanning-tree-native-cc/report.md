# maximum_spanning_tree (weighted): native kernel — 3.19x SLOWER -> 1.8-2.9x FASTER than nx (br-r37-c1-mstmaxnative)

## Problem
Weighted `maximum_spanning_tree` ALWAYS delegated to nx (full nx Kruskal +
`_from_nx_graph` rebuild) via a `_mst_has_weight_edge_attr` bypass — 3.19x slower
than nx — while `minimum_spanning_tree` used a fast native kernel. The bypass was
a stale "br-mstweightwrong" leftover; the native kernel was never updated.

## Three coordinated fixes (one lever: route weighted maximum to native)
1. KERNEL (lib.rs): the maximum kernel was the OLD pre-fix version — String
   `(min,max)` orientation (flips edges whose endpoints order differently as
   strings vs by index, diverging from nx) + `HashMap<&str>` union-find. Rewrote
   to mirror the minimum kernel (br-r37-c1-mstcsr): integer-CSR edge collection
   in nx's `G.edges()` order/orientation, descending *stable* weight sort (==
   nx's `sorted(reverse=True)`), integer union-find.
2. BINDING (algorithms.rs): removed the triple RuntimePolicy clone (clone +
   new_empty_with_policy + set) that deep-copied the source's unbounded decision
   ledger — the exact ~2x tax already removed from minimum
   (reference_runtime_policy_clone_tax). Use cheap `new_empty_with_mode`.
3. WRAPPER (__init__.py): drop the `_mst_has_weight_edge_attr` bypass; mirror
   minimum (sync edge attrs, reject NaN/inf -> nx parity, MultiGraph -> parity),
   then copy graph + node attrs onto the native result (the native binding
   preserves edge attrs + node identity but not graph/node attrs; nx does).

## Proof (behavior parity — absolute)
- 90 graphs (distinct + tie-heavy integer weights; graph attrs / node attrs /
  post-creation weight mutation / NaN / MultiGraph fallbacks): 0 mismatches on
  type, node-data, edge-set+weights, graph attrs.
- Golden sha256 == nx (`583e8738...`).
- `pytest -k spanning`: 320 passed.

## Result (median-of-7)
| n, m         | nx       | fnx (after) | speedup vs nx |
|--------------|----------|-------------|---------------|
| 500, 2500    | 3.42 ms  | 1.92 ms     | 1.78x         |
| 1000, 6000   | 10.40 ms | 3.60 ms     | 2.89x         |
| 2000, 12000  | 21.61 ms | 10.74 ms    | 2.01x         |

Before: 3.19x SLOWER (delegate + _from_nx_graph). After: 1.8-2.9x faster.
