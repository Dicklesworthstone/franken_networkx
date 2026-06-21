# Perf WIN + bugfix — size(weight) route through degree(weight): 0.45x->0.86x (br-r37-c1-sizedeg)

- Agent: `BlackThrush` · 2026-06-21 · File: `__init__.py`

## The gap
G.size(weight='weight') routed the str case to the native `size_impl`, which walks
`edges_ordered()` and does a PyO3 `get_item(attr).extract::<f64>()` on the live edge attr
dict PER EDGE — ~637us / 2000 edges = 0.45x vs nx. (Also raised TypeError on a callable
weight: the Rust binding's signature is `weight: str`.)

## The fix
Use nx's own formula `sum(d for _, d in self.degree(weight=weight)) / 2` for EVERY weight
type (the wrapper already used it for the callable case). Routes through the faster
degree(weight) path (~2x) and fixes the callable-weight TypeError. Byte-identical to size_impl
because degree counts each edge once per endpoint (self-loops twice) so /2 recovers the exact
per-edge weight sum.

## Verify
- vs nx 9000/9000 (str / None / callable weight; Graph/DiGraph/MultiGraph/MultiDiGraph;
  self-loops; negative + float weights). pytest -k 'size or weighted': all size tests pass.
  (2 pre-existing failures in test_second_order_centrality_woodbury_parity are UNRELATED —
  verified they still fail with this change stashed; second_order doesn't call G.size.)

## MEASURED
| op | before | after |
|----|--------|-------|
| G.size(weight) (2000 edges) | 0.45x (637us) | 0.86x (327us) |

~2x faster + a TypeError bugfix; residual 0.86x is degree(weight)'s own PyO3-per-edge floor.
