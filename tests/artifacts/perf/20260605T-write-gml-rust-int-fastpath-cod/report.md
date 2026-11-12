# perf reject: write_gml int/no-attr shortcut (br-r37-c1-43n6s)

## Target

Ready bead `br-r37-c1-43n6s` reported `write_gml` as 3.24x slower than
NetworkX on a 3,000-node / ~9,000-edge int-labeled graph. Fresh smoke on
current HEAD reproduced the gap:

- `to_dict_of_lists`: fnx/nx `0.59x`
- `write_adjlist`: fnx/nx `2.36x`
- `write_gml`: fnx/nx `3.36x`
- `write_edgelist`: fnx/nx `0.38x`

Fresh cProfile for 3 `write_gml` calls:

- total: `0.365s`
- `_fnx_to_nx`: `0.211s`
- `backend._fnx_to_nx`: `0.208s`
- `networkx.write_gml`: `0.154s`
- `_topo_emit_edges_by_adj`: `0.081s`
- native `_fnx.fnx_to_nx_adjacency`: `0.014s`

The native bulk adjacency binding was already being called once, so the bead's
"gate is not hit" hypothesis was stale. The actual residual is Python-side
conversion/topological edge emission plus NetworkX's writer.

## Attempted Lever

Tried a conservative fast path for exact simple `Graph`/`DiGraph` values with:

- `stringizer is None`
- int labels only
- empty graph/node/edge attrs

Two shapes were tested:

1. Route directly to the existing Rust GML writer. This was fast before rebuild
   but failed byte parity because undirected edge orientation used canonical
   storage order (`10,9`) instead of NetworkX adjacency orientation (`9,10`).
2. After fixing Rust GML undirected edge orientation and rebuilding, byte parity
   passed for the proof corpus, but the end-to-end route no longer cleared the
   keep gate.

The code and focused tests for this attempted lever were reverted.

## Same-Worker Evidence

Harness: `write_gml_fastpath.py`, with `fnx-before` forcing the old delegated
path by disabling the attempted predicate.

Proof after rebuild:

- cases: `8`
- failures: `0`
- golden SHA256: `a67dd340aed4be04245b4c0f24c83f9ba133b3dec037ef97bb2dd58ea22d4b2d`

Timing rows (`loops=5`, `repeat=9`):

- forced old fnx best: `0.030956429s/write`
- forced old fnx median: `0.037928833s/write`
- attempted fast path best: `0.040213302s/write`
- attempted fast path median: `0.044557577s/write`
- NetworkX best: `0.015446178s/write`
- NetworkX median: `0.016023754s/write`

Decision: reject. The attempted route regressed best time by `0.77x`
(`0.030956429 / 0.040213302`) and median by `0.85x`, so Score < 2.0.

## Next Primitive

Do not retry the narrow int/no-attr Python shortcut. The next viable primitive
needs to bypass NetworkX's writer entirely with a NetworkX-byte-compatible GML
emitter that preserves:

- dense numeric node ids in node iteration order
- original label stringization and escaping
- undirected edge orientation/order exactly as NetworkX emits it
- graph/node/edge attributes, including stringizer behavior or a strict fallback

The current Rust writer is close, but the win only matters if the public fast
path avoids an O(E) Python attr scan and still emits NetworkX-identical bytes on
the random corpus used by the bead.
