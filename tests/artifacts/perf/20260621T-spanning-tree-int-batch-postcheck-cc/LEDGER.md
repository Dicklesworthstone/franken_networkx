# FIX + SCOPE — min/max_spanning_tree int-batch weight-drop (post-check, no regression) + the broad weighted-kernel class

- Agent: `BlackThrush` · 2026-06-21 · MEASURED · __init__.py only

## Fixed
minimum_spanning_tree / maximum_spanning_tree returned an effectively UNWEIGHTED tree (size n-1)
on a fresh int-node `add_edges_from` graph — the native kruskal kernel reads edge weights from
the lazy mirror, which is unmaterialised for int-batch -> default-1 weights. Wrapped both with a
self-correcting POST-check (`_spanning_tree_int_batch_postcheck`): run the kernel, and only if
the source has attrs yet the result tree came back with NO edge attrs, materialise the mirror
(`edges(data=True)`, display-key path) and redo. Coerces for the probe so nx-graph input (whose
coercion ALSO yields int-batch) is covered. VERIFIED: fnx int-batch MST 116 / MAXST 246 (was 49);
nx-graph input MST 116 (was 49); 3 seeds all match; signatures preserved; conformance
spanning/mst/kruskal/prim/boruvka/operator_cross 1426 passed 0 failed.

## Why POST-check, not pre-emptive materialise (REVERTED that)
A pre-emptive `edges(data=True)` before the kernel REGRESSED weighted MST 0.69x -> 0.57x (the
materialise is O(E) PyO3 on EVERY call). The post-check probe early-exits on the result tree's
first weighted edge => O(1) for a normal graph => perf held at 0.70x (HEAD 0.69x). Pre-emptive
inline edits to minimum_spanning_edges + minimum_spanning_tree were reverted.

## BROAD SCOPE still open (the construction root)
~40 `_sync_rust_edge_attrs` call sites precede native kernels that read the lazy mirror; ANY of
them is wrong on a fresh int-batch weighted graph. `_sync_rust_edge_attrs` (mirror->inner) is a
no-op for the empty int-batch mirror, and the inner itself is MIS-KEYED by the int add_edges_from
construction (the same canonical-vs-display-key inconsistency that broke to_directed / the fnx->nx
conversion). The shortest-path family (dijkstra/bellman/astar/floyd/pagerank/to_numpy) is
UNAFFECTED — it reads the inner correctly. Remaining graph-returning weighted fns can take the
same post-check; scalar/generator ones (minimum_spanning_edges) need either a tight lazy-gate or
the real cure: fix the int-batch construction key consistency (qq6hi sibling,
reference_lazy_key_canonical_divergence). Post-check is the non-regressing per-fn workaround until
then.
