# MultiGraph/MultiDiGraph add_edges_from O(E^2)->O(E), 30.7x/10.1x (br-r37-c1-mgaddedges)

## Structural defect (per no-ceiling addendum: complexity-class fix)
`_multi_add_edges_from` computed each parallel edge's auto-key with
`self.has_edge(u,v)` + `self[u][v]` (gap-aware: `key=len(existing); while key in
existing: key+=1`). Every `self[u][v]` REBUILT the full MultiAdjacencyView —
O(E), since the view cache is invalidated by the per-edge edges_seq bump — making
bulk construction O(E^2). Measured: MultiGraph add_edges_from(20k edges) = 4900ms
(130x slower than nx); MultiDiGraph 1463ms (35x). This flows into every multigraph
builder (union/compose/copy/from_*/read_*/generators on Multi types).

## Lever (O(1) keydict)
Replace `self[u][v]` with the native O(1) `get_edge_data(u, v)` keydict (1us even
on a 20k-edge graph) for the SAME gap-aware key computation, and route the attr
mutation through O(1) `get_edge_data(u, v, key)` (live dict) instead of
`self[u][v]`. The native add_edge returns the key actually used (auto-assigns
when None). O(E^2) -> O(E).

## Isomorphism (bit-exact, incl. the subtle gap case)
The gap-aware key (len + increment past existing) is preserved EXACTLY — required
when explicit keys are interleaved with auto-keys for the same (u,v) (a naive
"native auto-key" diverges; the golden caught it). Golden 0-mismatch vs nx over
MultiGraph + MultiDiGraph x 4 seeds x {2-tuple, data-dict, explicit-key 3-tuple,
4-tuple, 'key'-in-datadict collision} x {no global attr, global color=red},
comparing edges+keys+data:

    mismatches=0
    MGADD_GOLDEN d022a3fcbbbf640a8958629e3e42cd3986b3adb1d39267ea99c681c07495c89c

1494 multigraph/add_edge pytest + union/compose/copy/convert/readwrite suites pass.

## Benchmark (add_edges_from, 20k edges, median)

    MultiGraph    4899.7 -> 159.8 ms  = 30.7x self  (130x -> 4.19x vs nx)
    MultiDiGraph  1463.4 -> 144.4 ms  = 10.1x self  ( 35x -> 3.53x vs nx)

Eliminates the pathological O(E^2). Residual ~4x vs nx is the per-edge dual-rep
construction tax (br-r37-c1-71x9k, the bulk/arena rewrite — next primitive).
Score = Impact 5 x Confidence 5 / Effort 2 = 12.5. Pure-Python.
