# Perf win — tree_data bulk snapshot (br-r37-c1-treedatabulk)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/__init__.py`

tree_data serialized a rooted directed tree via a per-node `list(G[node])`
AdjacencyView crossing + `{**G.nodes[child]}` AtlasView crossing for the build,
AND a per-node `G[node]`/`G.predecessors` crossing for the weakly-connected
validation — 2-3 PyO3 view crossings per node vs nx's plain dict access.

Lever: snapshot the successor adjacency (`G.adjacency()`) and node attrs
(`G.nodes(data=True)`) in ONE native crossing each; derive predecessors as the
cheap O(E) transpose of the successor snapshot (no extra crossing); run both the
weakly-connected DFS and the nested-payload build off the snapshots. Exact DiGraph
only; subclasses/MultiDiGraph keep the per-node path.

## Win vs NetworkX 3.6.1 (pinned taskset -c 2, warm min-of-20, 2000-node tree)

| tree_data(root) | before | after |
| --- | ---: | ---: |
| | 0.40x (4.58ms) | **1.12x** (1.64ms) — 2.8x self-speedup |

## Parity

800 random directed trees: node attrs, id/children attr-key collisions, custom
ident/children kwargs, and not-a-tree / undirected / disconnected error contracts
— 0 mismatches. pytest -k 'tree or json or serializ or readwrite' passed.
