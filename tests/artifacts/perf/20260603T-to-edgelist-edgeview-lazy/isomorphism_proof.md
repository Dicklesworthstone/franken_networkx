# br-r37-c1-gl3nq Isomorphism Proof

## Profile-backed target

Baseline profile, `bench_to_edgelist.py profile --case to_edgelist --repeat 20`, showed 1.888s cumulative time in Python `to_edgelist`/`_DiGraphEdgeView.__call__` adjacency wrapper materialization for a directed sparse graph with 16,399 edges.

## One optimization lever

Add one native exact-simple-graph fast path, `_fnx.to_edgelist_simple`, and call it only from `to_edgelist(G, nodelist=None)` when `type(G) is Graph or type(G) is DiGraph`. Multigraphs and `nodelist` cases stay on the existing Python path.

## Behavior invariants

- Ordering: native path iterates `inner.edges_ordered()`, the same insertion-ordered edge source used by the graph storage.
- Tie-breaking: no algorithmic tie-break policy is introduced or changed; this is edge projection only.
- Floating point: edge attributes are not transformed, rounded, compared, or recomputed.
- RNG: no generator or seed logic is touched.
- Attribute identity: the native path returns cloned Python references to the existing edge attribute dictionaries, not copied dict payloads.
- Return surface: Python still wraps the returned list with `_guarded_edge_list`, preserving current fnx list-like behavior and mutation guard semantics.
- Scope guard: exact `Graph`/`DiGraph` only, no subclasses, no multigraphs, no `nodelist`.

## Golden output

Baseline SHA256: `f749a0821055e92da035534a0c2c564f4a3d7f44da6ca82f410a50d2a26e653d`

After SHA256: `f749a0821055e92da035534a0c2c564f4a3d7f44da6ca82f410a50d2a26e653d`

The golden payload checks edge order, serialized edge/data content, and live first-edge attribute dictionary identity against the same graph construction.

## Bench delta

Direct rch benchmark:

- `to_edgelist`: 0.0633533056s -> 0.0112149593s, 5.65x faster.
- `list(to_edgelist)`: 0.0798505121s -> 0.0232189760s, 3.44x faster.

Hyperfine rch process-level benchmark, including interpreter startup and graph construction:

- `to_edgelist`: 627.0ms +/- 22.5ms -> 565.6ms +/- 21.1ms.
- `list(to_edgelist)`: 643.9ms +/- 30.0ms -> 591.3ms +/- 34.2ms.

After profile shifted the hot path to `{built-in method franken_networkx._fnx.to_edgelist_simple}` with 0.203s cumulative time for 20 calls.

## Score

Impact 4 x Confidence 4 / Effort 3 = 5.33. Kept.
