# Alien Recommendation Card: br-r37-c1-xykjs

## Profile Symptom

`_fnx_to_nx` is on every NetworkX-delegation path. On a BA(3000, 4)
simple graph, the fallback path spent 0.837 s cumulative in three
conversions under cProfile. The dominant avoidable work was per-edge
Python adjacency-view access:

- `__init__.py:_atlas`: 0.263 s cumulative
- `__init__.py:__getitem__`: 0.242 s cumulative
- `backend.py:_topo_emit_edges_by_adj`: 0.199 s cumulative

## Matched Primitive

Alien graveyard match: column/SoA-style bulk materialization and
vectorized execution principles (§7.10, §8.2): replace tuple-at-a-time
boundary crossings with a contiguous/bulk dump of the exact structure the
interpreter will consume.

Applied primitive: one PyO3 crossing returns `(node, [(neighbor, attrs)])`
in node-insertion order and adjacency-insertion order, reading the fresh
Python `edge_py_attrs` store.

## Recommendation

Implement `_fnx.fnx_to_nx_adjacency(G)` for concrete simple `Graph` and
`DiGraph`, then feed the existing Python topological edge emitter with
the native neighbor lists. Keep all multigraphs, views, subclasses, and
helper-unavailable cases on the Python AtlasView fallback.

## EV Score

- Impact: 4 - hits every delegated NetworkX parity conversion.
- Confidence: 5 - behavior is constrained by byte-identical conversion
  digests and an existing fallback.
- Effort: 2 - one Rust helper plus Python routing.
- EV: `4 * 5 / 2 = 10.0`.

## Fallback

If any graph is not an exact concrete simple fnx graph, or if the native
helper is unavailable, `_fnx_to_nx` keeps the AtlasView Python path.
