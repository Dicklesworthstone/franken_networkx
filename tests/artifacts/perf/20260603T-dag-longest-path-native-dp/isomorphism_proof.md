# Isomorphism Proof

## Ordering And Tie-Breaking

NetworkX computes `dist[v]` by iterating `G.pred[v].items()` and then uses `max(us, key=lambda x: x[0])`. Python's `max` is stable for equal keys, so the first predecessor in `pred[v]` insertion order wins.

The new exact-`DiGraph` path uses `_native_in_edges_data_key`, whose source order is target-node order and then predecessor insertion order. Grouping those triples by target preserves the same predecessor order seen by `G.pred[v].items()`. The DP, stable `max`, negative-distance reset, final `max(dist, key=...)`, and path reconstruction loop are byte-for-byte equivalent to the generic wrapper logic.

Explicit `topo_order` stays on the old path, so caller-supplied ordering behavior and error surfaces are unchanged.

## Edge Weights

The native snapshot receives the same `weight` key and `default_weight` value that the old `data.get(weight, default_weight)` path used. It reads the live Python edge-attribute dictionaries and returns the same value that the old predecessor-view loop would have read. Addition, comparison, `TypeError`, `NaN`, `inf`, integer return types, boolean weights, and mixed numeric behavior remain Python operations in the same DP.

Multigraphs remain on the old path, preserving the heaviest-parallel-edge selection.

## RNG And Floating Point

The algorithm uses no RNG. The benchmark fixture uses deterministic `random.Random(20260603)` only to construct the graph before timing. Floating-point behavior is unchanged because edge-weight arithmetic and comparisons still occur in Python with the same values and ordering.

## Golden Output

The output payload includes the longest path, length, node runtime types, and length runtime type. SHA256 is identical across baseline FNX, NetworkX oracle, and after FNX:

`5b8012a4dd619416733afe7f6475760247475c466e9c3975cfb60f6827688161`

