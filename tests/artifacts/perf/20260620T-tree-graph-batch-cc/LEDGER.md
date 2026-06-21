# Perf win — tree_graph batch construction (br-r37-c1-treegraphbatch)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/__init__.py`

tree_graph reconstructed a tree via a per-node `add_edge` + `add_node` PyO3
round-trip during the recursion (the construction tax) — 0.42x nx (no node attrs),
0.40x (attrs).

Lever: collect (parent, child) edges + per-node data in DFS pre-order, then build
in one batch. NO node attrs (the common tree round-trip): `add_edges_from` alone
creates every node in the exact nx order (root via add_node, each child when its
parent edge is added) -> 1.15x WIN. WITH attrs: `add_nodes_from`(attrs) before
`add_edges_from` -> 0.88x (loss-reduction; residual is the construction floor vs
nx's native-dict per-element build, [[reference_construction_tax_relabel_lever]]).

## vs NetworkX 3.6.1 (pinned taskset -c 2, warm min-of-20, 2000-node tree)

| tree_graph(data) | before | after |
| --- | ---: | ---: |
| no node attrs | 0.42x | **1.15x** |
| node attrs | 0.40x | 0.88x |

## Parity

800 random tree_data round-trips: node attrs, id/children attr-key collisions,
custom ident/children kwargs, single-node trees — 0 mismatches (node order, edges,
node attrs, graph attrs). pytest -k 'tree_graph or tree_data or json' 35 passed.
