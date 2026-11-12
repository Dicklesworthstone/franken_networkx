# perf(add_edges_from): Graph batch short-circuit (br-r37-c1-u2jod)

## Lever
DiGraph/MultiGraph expose `_try_add_edges_from_batch`; the wrapper's batch
short-circuit (`if native_batch(ebunch): return`) fires for them, SKIPPING the
per-edge Python validation loop. PyGraph did NOT expose it, so every plain Graph
`add_edges_from(list/tuple)` paid the O(E) Python validation loop before reaching
the (already fast) native batch via `raw(materialized)`.

Added a `_try_add_edges_from_batch` pymethod to PyGraph that chains the two
proven collect-then-commit batches the native `add_edges_from` already uses —
`try_add_plain_edge_batch` then `try_add_attr_edge_batch`. Returns true only when
the batch fully replicated valid input (wrapper safely skips validation);
otherwise false → wrapper's per-edge loop runs unchanged (owns all error /
partial-prefix contracts). NO `__init__.py` change — the wrapper already calls
`getattr(self, "_try_add_edges_from_batch")`.

## Proof (byte-identical)
14-scenario corpus (plain_int/plain_str/weighted/mixed_2_3/tuple_nodes/global_attr/
with_dups/list_edges/bad_arity/none_node/preexist/gen_weighted/big_weighted):
- OLD installed: PARITY_OK, sha 07afa568de2d3956858398141c726e2ed711426911f04034c136a55ecbbb243d
- NEW build:     PARITY_OK, sha 07afa568de2d3956858398141c726e2ed711426911f04034c136a55ecbbb243d  (IDENTICAL)
- Matches genuine nx on every scenario (incl. error classes for bad_arity/none_node).
- 379 construction/edge tests pass on the new build (the 1 failure,
  test_graph_iteration_detects_batch_node_mutations, is PRE-EXISTING — fails
  identically on the old build, unrelated to this change; bead filed).

## Bench (warm min-of-N, add_edges_from 20k)
- int 2-tuple:      before 1.57x slower -> after 1.24x  (validation loop skipped)
- weighted 3-tuple: before 2.45x slower -> after 2.13x  (validation loop skipped;
  residual is the architectural eager edge-attr Py mirror — materialize_edge_py_attrs
  returns empty rather than reconstructing from inner, and inner can go stale, so
  lazy edge attrs are unsafe without a bigger refactor. Deferred.)
