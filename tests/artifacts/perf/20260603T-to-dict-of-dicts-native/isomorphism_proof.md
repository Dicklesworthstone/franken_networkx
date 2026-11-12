# to_dict_of_dicts native fast path (br-r37-c1-yl59j)

## Change
`to_dict_of_dicts` built `{u: {v: edge_data}}` with a pure-Python double loop
over `G[u].items()`, paying the slow per-access AdjacencyView/AtlasView Python
machinery for every (u,v) -> ~233x slower than networkx.

Added a native `_fnx.to_dict_of_dicts_undirected(G)` (crates/fnx-python/src/
readwrite.rs, registered in that module's own `register()` -- no reserved-file
edits) that walks the inner adjacency in order and reuses the LIVE
`edge_py_attrs` `Py<PyDict>` objects (the exact references `G[u][v]` returns).
The Python wrapper calls it only when `nodelist is None and edge_data is None
and type(G) is Graph`.

## Why output is bit-identical
- Keys: `pg.inner.neighbors_iter(u)` iterates the same inner adjacency that the
  AdjacencyView does, so each inner dict's KEY ORDER is the node's adjacency
  order -- identical to nx and to the old path (verified: 0 key-order mismatches
  across 5 graphs; an edges()-based build was rejected because it reordered keys).
- Values: `edge_py_attrs[edge_key(u,v)]` is the same object as `G[u][v]`, so
  `d[u][v] is G[u][v]` holds (live, mutation-visible) -- matching nx's shared-
  datadict semantics. Verified by reference-identity + mutation assertions.
- `type(G) is Graph` (exact) excludes DiGraph/MultiGraph, Python subclasses, and
  filtered SubgraphViews (avoids the _coerce/SubgraphView bypass trap); those
  plus any `nodelist`/`edge_data` use take the unchanged general path.
- Self-loops: neighbors_iter yields u for (u,u); d[u][u] set once. No FP/RNG.

## Verification
tdod_golden.py: structure + inner-dict key order + edge-data values vs networkx
across BA(1500,4)/(300,3)/(80,5)/(40,2)/(10,3) (with weighted edges). 0
mismatches:

    TDOD_GOLDEN 8933c83e74c9bf74181ffc5bb94effd15250af0b6d677dfd393ba6ea6bc6ccff

45 convert/dict pytest cases + clippy -D warnings pass.

## Benchmark (BA(1500,4), median of 9)
    before: 60.65 ms
    after :  2.72 ms   -> 22.3x  (nx: 0.23 ms)

Opportunity Score = Impact 5 x Confidence 5 / Effort 2 = 12.5.
