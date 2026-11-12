# NEGATIVE EVIDENCE — MultiGraph.copy() clone+reorder does NOT port from MultiDiGraph (br-r37-c1-mdgcopyclone)

- Agent: `BlackThrush` · 2026-06-21 · File: `crates/fnx-python/src/lib.rs` (NOTE only)

## What was tried
Applied the MultiDiGraph clone fix (e75a123b9, 0.61x->1.86x) to MultiGraph._native_copy:
inner.clone() + clone mirrors + reorder_rows instead of the edge-by-edge rebuild. Measured
0.80x -> 3.27x and byte-exact 2000/2000 on FRESH graphs + independence + identity.

## Why it was REVERTED
pytest test_roundtrip_of_copy_keeps_walk_reordered_rows[MultiGraph] FAILED. Root cause:
MultiGraph's `reorder_rows_for_nx_copy_walk` is INPUT-ORDER DEPENDENT — early neighbours
sort by (pos(v), index-of-u-WITHIN-adj[v]), so the result depends on the row order it runs
on. The old rebuild always feeds it edge-INSERTION order (via edges_ordered()); an inner
clone feeds the SOURCE's current order, which for a copy-of-a-copy is already u-major
reordered -> diverges. The directed sibling is SAFE because reorder_pred rebuilds pred from
the never-reordered succ (insertion order), so it is input-order independent.

## Outcome
Reverted to the rebuild + left an in-code NOTE so this isn't re-attempted. MultiGraph.copy()
stays ~0.88x (String substrate). MultiDiGraph.copy() win (1.86-2.12x) is unaffected. To win
MultiGraph.copy() one would first need an input-order-INDEPENDENT reorder_rows (rebuild rows
from a canonical walk, like reorder_pred does for the directed pred) — scoped follow-up.
