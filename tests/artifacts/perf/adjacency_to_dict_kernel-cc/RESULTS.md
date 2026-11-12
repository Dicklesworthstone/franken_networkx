# G.adjacency() — route to the to_dict_of_dicts native kernel

## Lever
Graph/DiGraph.adjacency() built its ``{node: {nbr: edge_attrs}}`` snapshot via the
``_native_adjacency_dict`` binding, which re-materialises each edge's attr dict
through a slower path (~1.13ms@n=800). The ``to_dict_of_dicts`` native kernel
(``_fnx.to_dict_of_dicts_undirected``, also serves DiGraph successors) builds the
IDENTICAL structure — same node x neighbour order, and the inner dicts are the
SAME live objects (``d[u][v] is G[u][v]``, so live-mutation still propagates) —
~15x faster. adjacency() now iterates ``to_dict_of_dicts_undirected(self).items()``;
falls back to the legacy binding / AtlasView path for subclasses the kernel declines.

## Isomorphism (byte-identical to PRIOR fnx output)
fnx-own adjacency signature (node order, neighbour order, edge-attr item list)
is IDENTICAL before and after: sha fc7bd39011641ed1 unchanged across 16
Graph/DiGraph cases (with and without edge attrs). Inner-dict object identity
(``adj[u][v] is G[u][v]``) preserved. 527 adjacency/to_dict_of_dicts tests pass.

NOTE: fnx.adjacency() iteration ORDER already differs from nx's for some
randomly-built graphs (8/16 cases) — a PRE-EXISTING divergence (BEFORE had the
same 8), unchanged by this commit (BEFORE-fnx sha == AFTER-fnx sha).

## Benchmark (warm min) — ratio = nx/fnx
| graph     | BEFORE fnx      | AFTER fnx       | self-speedup |
|-----------|-----------------|-----------------|--------------|
| BA(400)   | 0.548ms         | 0.046ms         | 11.9x        |
| BA(800)   | 1.18ms          | 0.105ms         | 11.2x        |
| BA(1500)  | 2.2ms           | 0.218ms         | ~10x         |

dict(G.adjacency()) gap to nx narrows from ~65-73x slower to ~5-6x (~11x
self-speedup). The residual is fundamental: nx's adjacency() yields live _adj[n]
references (~zero construction), while fnx must build the nested dict from Rust
storage. Benefits every adjacency() consumer. (br-r37-c1-9hkgu, partial)
