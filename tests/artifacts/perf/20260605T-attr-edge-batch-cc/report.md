# perf: attributed add_edges_from batch path (br-r37-c1-pr8q6)

## Problem

Plain (u, v) batches were already bulk-inserted (kt0vp:
`extend_edges_unrecorded`), but ATTRIBUTED edges — (u, v, dict), the
shape every conversion/operator path produces — fell into the per-edge
`add_edge`, paying a `record_decision` ledger push (timestamp syscall +
several String allocs) plus full add_edge machinery PER EDGE. Sweep
(worktree HEAD, warm min-of-9, n=1500/E=5217): add_edges_from(data)
6.08x vs nx; feeds compose 6.00x, disjoint_union 6.28x,
from_dict_of_dicts 7.44x, DiGraph(G) 11.44x.

## Lever (one)

1. fnx-classes: `Graph::extend_edges_with_attrs_unrecorded` — attributed
   sibling of `extend_edges_unrecorded`. Insert-or-MERGE (duplicate
   edges extend their AttrMap, matching `add_edge_with_attrs`), node
   auto-creation in first-appearance order, identical adjacency /
   adj_indices / edge_index_endpoints maintenance, ONE summary ledger
   record. Revision bumped when a merge changes attrs (cache safety).
2. fnx-python PyGraph: `collect_attr_edge_batch` (pure collect, NO
   mutation — bails to the per-edge loop on ANY non-replicable item:
   non-tuple, bad arity, non-dict third, non-plain endpoint,
   unconvertible attr value, `__fnx_incompatible` keys) +
   `add_attr_edge_batch` (PyDict mirrors entry+update — merge semantics
   identical to per-edge — then one bulk inner call) + hook in
   `add_edges_from` after the plain batch.

Eager AttrMap conversion is KEPT (no lazy-sync — the g5ifq revert showed
that breaks weighted kernels). Error/partial-prefix contracts unchanged:
the batch never commits partially; anything anomalous re-runs the
existing per-edge loop from scratch.

## Parity proof (parity_proof.py)

90-case differential vs nx: random attributed batches straddling the
MIN=8 gate (mixed 2-/3-tuples, dup edges both directions, self-loops,
int/str/float/tuple keys, varied value types), merge-into-preexisting,
global **attr, list-of-lists, bad-arity/None/unhashable partial-prefix,
source-dict aliasing, dijkstra + weighted degree exactness post-batch.

- after-change: 80 passed / 10 failed
- HEAD (same suite, same seed): 80 passed / SAME 10 failed
- GOLDEN_CORPUS_SHA256 identical before/after:
  275c260de2862d3a7ff011dd1c3d72c59f469573a19bed70df3a57129b1de173

=> the change is observationally invisible except for speed. The 10
failures are PRE-EXISTING parity bugs, now filed: br-r37-c1-z6uka
(mixed int/float node-key display in batch paths) and br-r37-c1-a4zlp
(non-dict third element: missing endpoint node in partial error state).

## Bench (warm min-of-9, n=1500/E=5217, same host/window)

- add_edges_from(data):  19.4ms -> 8.4ms; 6.08x -> 2.82x vs nx (2.3x self)
- compose:               42.8ms -> 26.7ms; 6.00x -> 3.94x
- add_edges_from(nodata): unchanged 2.4x (plain batch path, untouched)
- from_dict_of_dicts / DiGraph(G): unchanged (route through per-edge
  Python add_edge / copy-constructor — next levers, see bead notes)

Residual 2.82x = canonicalization + PyDict mirror allocs + CGSE AttrMap
conversion (dual-rep substrate, br-r37-c1-w1dm8 / 71x9k).

## Validation

- tests/python/test_add_edges_attr_batch_parity.py: 10 passed
- fnx-classes unit test extend_edges_with_attrs_unrecorded_matches_add_edge_with_attrs: ok (63 passed total)
- full tests/python suite: 21322 passed; 6 failures identical to HEAD
  (verified pre-existing this session, multigraph/coverage domains)
- clippy -p fnx-classes -p fnx-python --release: no new warnings
- Built/tested in isolated worktree (HEAD + only my hunks; peer's
  in-flight PyMultiGraph hunks in shared lib.rs filtered out via patch)
