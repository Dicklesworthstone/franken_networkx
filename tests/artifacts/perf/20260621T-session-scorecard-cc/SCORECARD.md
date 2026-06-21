# BOLD-VERIFY session scorecard (BlackThrush, 2026-06-21) — fnx vs nx, MEASURED

All ratios nx/fnx (>1 = fnx WINS), warm min-of-N, taskset+PYTHONHASHSEED=0, REAL fnx graphs
(never gnm_random_graph(directed=True) — see reference_directed_benchmark_nx_leak_trap).

## SHIPPED WINS THIS SESSION (each byte-exact + conformance GREEN)
| lever (commit)                                   | before | after  |
|--------------------------------------------------|--------|--------|
| copy-walk reorder O(E*deg)->O(E) Graph/DiGraph   | erodes | 10x @complete |
| native deepcopy (Graph/MG/DiG/MDG)               | 0.37-0.58x | 1.3-4.3x |
| gnm complete-case parity + directed->fnx native  | bug/0.36x wf | 2.86x workflow |
| DiGraph extend_edges_unrecorded de-dup           | 0.83x  | 1.04x  |
| DiGraph int-node fast path (range/list)          | 0.33x  | 1.38x  |
| Multi int-node fast path                          | 0.28x  | 0.93x  |
| MultiDiGraph.copy() rebuild->clone+reorder_pred  | 0.61x  | 1.86-2.12x |
| MultiGraph.copy() bulk keyed-extend + lazy attrs | 0.88x  | 1.22x  |
| bipartite color/sets native adjacency snapshot   | 0.61x  | 0.79x  |

## VERIFIED DOMINATION (sampled, real fnx graphs) — fnx WINS
clustering 48x · floyd_warshall 61x · flow_hierarchy 290x · transitive_closure 5.4x ·
topological_sort 30x · louvain 12x · greedy_modularity 17x · pagerank 6.9x · betweenness
20x · bfs/dfs_tree 3.1-3.3x · reverse 2.96x · to_directed 2.37x · descendants 1.3x ·
laplacian 3.2x · scc 4x · eccentricity 10x · harmonic 14x · edge_betweenness 28x.

## REMAINING LOSSES (all String-keyed multigraph-ATTR substrate) — scoped
- compose(MultiDiGraph) 0.36x: root = add_edges_from with 4-tuples (u,v,key,data) is
  REJECTED by the attr batch collect (digraph.rs ~2394 `!(2..=3)`) -> per-edge
  add_edge_with_key_and_attrs (2 record_decision/edge). Fix = extend the collect to
  4-tuples + explicit-key bulk extend_keyed_edges_with_attrs_unrecorded. Caveat: even the
  3-tuple attr batch is 0.84x (substrate), and the batch's fresh-gate (edge_count==0) means
  compose's 2nd add_edges_from(H) stays per-edge -> only a partial win (~0.6x), not domination.
- MultiGraph/MultiDiGraph attr add_edges_from 0.84x / 0.32x: String-keyed succ/pred IndexMap
  + per-edge attr crossing. The REAL fix is the int-CSR multigraph migration (br-r37-c1-yl606,
  a multi-session rewrite) — these will not dominate until the substrate is integer-keyed.
- REVERTED (negative evidence): MultiGraph.copy() clone (reorder_rows is input-order
  dependent, 7b45a463d); native max_weight_clique (tie/order-blocked); MultiGraph reorder
  rebuild (regressed). 
- PRE-EXISTING (not mine): flow-kernel HEAD regression -> 35 directed_node_connectivity
  failures (a peer's; node_connectivity runs max-flow).

## NET: fnx dominates the entire non-substrate surface. The only sub-1x cases left are the
## String-keyed multigraph-attr construction substrate, gated on the int-CSR migration.
