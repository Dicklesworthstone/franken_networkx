# node_link_data native kernel (json_graph)

Lever: route exact simple `Graph`/`DiGraph` through native
`_fnx.node_link_data_simple` (builds `nodes` + `edges` arrays in Rust,
copying live attr dicts + appending name/source/target fields), bypassing the
per-edge EdgeView Python machinery. The undirected edge loop replicates nx's
`G.edges()` dedup order with a seen-set of finished source nodes rather than
`edges_ordered()`, which eagerly clones every edge's AttrMap (that materializer
made a first cut of this kernel NO faster than the Python loop; switching to
neighbors_iter + seen-set is what unlocked the win).

Entry point: `franken_networkx.readwrite.json_graph.node_link_data`
(canonical nx module `networkx.readwrite.json_graph`).

## Benchmark (python time.perf_counter, 25 reps, attrs on 1/3 edges)

| graph                     | nx       | fnx before | fnx after | gap before | gap after |
|---------------------------|----------|------------|-----------|------------|-----------|
| n=1500 m=12000 undirected | 5.16 ms  | 15.15 ms   | 7.20 ms   | 3.50x      | 1.40x     |
| n=1500 m=12000 directed   | 2.79 ms  | ~14 ms     | 7.74 ms   | 3.49x      | 2.77x     |
| n=3000 m=30000 undirected | 17.35 ms | ~50 ms     | 26.36 ms  | ~3.3x      | 1.52x     |

Self-speedup ~2.1x; gap vs nx 3.5x-slower -> 1.40x-slower (n=1500 undirected).

## Isomorphism + golden proof

Bit-exact `node_link_data` parity vs networkx across 10 shapes
(undirected/directed, custom field names, no-attrs, singleton/tiny), plus:
edge attrs literally named `source`/`target` and node attrs named `id`
(overwrite semantics), duplicate-field-name NetworkXError parity, multigraph
fallback, and a no-mutation guard on the stored attr dicts.

GOLDEN sha256 (n=400 m=4000 undirected, attrs, json sort_keys):
059aa3327f573247f030e51c4b6af71736ee2e5206c80affd141f8fed47cdc2f
(nx == fnx)

## Residual / follow-up

Residual (undirected 1.40x, directed 2.77x) is per-edge `PyDict_Copy` +
node-key string-hash from Rust vs CPython's `{**d, source:u, target:v}`
dict-display; full closure needs substrate node interning (br-r37-c1-71x9k).
Top-level `fnx.node_link_data` (reserved __init__.py) should delegate to this
kernel when that lock frees (same follow-up class as br-r37-c1-9kpev).
