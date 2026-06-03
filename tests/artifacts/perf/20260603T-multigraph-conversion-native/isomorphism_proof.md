# br-r37-c1-e6olo isomorphism proof

Golden output:
- Before SHA256: `361a074a7a10fe7f6d705c938c3af917c83792e8e560044912aa742384dcbad6`
- After SHA256: `361a074a7a10fe7f6d705c938c3af917c83792e8e560044912aa742384dcbad6`
- Harness: `bench_multigraph_conversion.py --mode golden --nodes 80 --edges 400`
- All four default conversions matched NetworkX in the golden payload.

Supplemental reciprocal oracle:
- Artifact SHA256: `bfa719b4a7f3d5cb2447f87e7564637ffe627a6b9951e7c92579b14c3344e49a`
- Values checked: `False`, `True`, `None`, `1`
- All cases matched NetworkX; only literal `reciprocal is True` filters.

Ordering and tie-breaking:
- Node materialization uses `nodes_ordered()`, preserving source insertion order.
- `MultiGraph.to_directed()` iterates node order, neighbor order, then edge-key order to match NetworkX adjacency traversal and duplicate reverse orientations.
- `MultiGraph.to_undirected()` uses ordered edge snapshots to preserve public endpoint orientation.
- `MultiDiGraph.to_directed()` uses successor adjacency order.
- `MultiDiGraph.to_undirected(reciprocal is not True)` uses successor adjacency order and updates same undirected key collisions in the same observable order as `MultiGraph.add_edge`.
- Public edge-key display is preserved with the stored Python key object when present.

Deep copy:
- Graph, node, and edge attribute dictionaries use Python `copy.deepcopy`.
- Golden payload includes independence checks for nested graph/node/edge payloads.

Fallback surface:
- `as_view=True` still returns the existing view path.
- Subclasses, private NetworkX storage overrides, and custom `to_directed_class()` / `to_undirected_class()` factories stay on the generic Python path.

Floating point and RNG:
- Conversion code performs no floating-point arithmetic and makes no random calls.
- Harness randomness is fixture generation only, using deterministic seeds.

