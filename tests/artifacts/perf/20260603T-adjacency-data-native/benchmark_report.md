# adjacency_data native kernel (json_graph)

Lever: route exact simple `Graph`/`DiGraph` through native
`_fnx.adjacency_data_simple` (builds `nodes` + `adjacency` arrays in Rust,
copying live attr dicts + appending `id_`), bypassing the per-edge
AdjacencyView Python machinery in the pure-Python wrapper.

Entry point: `franken_networkx.readwrite.json_graph.adjacency_data`
(canonical nx import path `networkx.readwrite.json_graph.adjacency`).

## Benchmark (python time.perf_counter, 20 reps, attrs on 1/3 edges)

| graph                     | nx       | fnx before | fnx after | self-speedup | vs nx after |
|---------------------------|----------|------------|-----------|--------------|-------------|
| n=1500 m=12000 undirected | 6.085 ms | 94.239 ms  | 16.002 ms | 5.9x         | 2.63x slow  |
| n=1500 m=12000 directed   | 3.086 ms | ~          | 10.817 ms | ~            | 3.50x slow  |
| n=3000 m=30000 undirected | 27.506ms | ~          | 49.128 ms | ~1.9x        | 1.79x slow  |

Gap vs nx: 14.28x-slower -> 2.63x-slower (n=1500). Score >> 2.0
(self-speedup 5.9x, behavior-preserving).

## Isomorphism + golden proof

Bit-exact `adjacency_data` parity vs networkx across 9 shapes
(undirected/directed, custom id field, no-attrs, singleton, empty) x default
+ custom-attrs, plus multigraph fallback. Stored attr dicts are NOT mutated.

GOLDEN sha256 (n=300 m=3000 undirected, attrs, json sort_keys):
73704ad0fefeb35abb76cea796788aaa03f087b7a3905568e1e259e6018aa24d
(nx == fnx)

## Residual / follow-up

Residual 2.63x is per-edge `PyDict_Copy` + node-key string-hash from Rust vs
CPython's optimized `{**d, id_: v}` dict-display bytecode. Closing it needs
substrate node interning (deferred br-r37-c1-71x9k). Top-level
`fnx.adjacency_data` (in the reserved __init__.py) should delegate to this
native path when that lock frees.
