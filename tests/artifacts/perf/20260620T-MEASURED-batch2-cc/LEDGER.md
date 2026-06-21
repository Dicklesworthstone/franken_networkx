# MEASURED warm bench batch 2 — redundant-conversion + projection levers (br-r37-c1-measuredbatch)

- Agent: `BlackThrush` · 2026-06-20 · warm min-of-12 (warmup 5), `taskset -c 2 PYTHONHASHSEED=0`,
  existing install. nx/fnx = nx_time/fnx_time (>1 = fnx WINS). Complements batch 1 (generators).

## CONFIRMED WINS (fnx > nx) — the redundant-conversion + projection vein is the cleanest
| function                  | nx/fnx | lever |
|---------------------------|--------|-------|
| transitive_closure(n=60)  | 4.88x  | return fnx directly, skip _from_nx_graph (tcnoconv) |
| contracted_nodes          | 4.25x  | return fnx directly + contraction-attr correctness fix (contractnoconv) |
| weighted_projected_graph  | 2.00x  | snapshot-adjacency native projection |
| dfs_tree                  | 1.77x  | return fnx directly, skip _from_nx_graph |
| bfs_tree                  | 1.75x  | return fnx directly, skip _from_nx_graph |
| projected_graph UNDIR     | 1.47x  | snapshot-adjacency native projection |
| transitive_reduction(60)  | 1.19x  | (batch 1) skip 2x conversion |
| random_tournament(60)     | 1.02x  | neutral — DiGraph(edges) construction ~= nx |

## Session net measured picture (batches 1+2)
CLEAN WINS (fnx>nx, int-CSR result types / conversion-skips):
  transitive_closure 4.88x, contracted_nodes 4.25x, threshold_graph 3.10x,
  weighted_projected_graph 2.00x, complete_bipartite 1.90x, from_prufer 1.84x,
  dfs_tree 1.77x, bfs_tree 1.75x, random_graph(undir) 1.50x, projected_graph(undir) 1.47x,
  transitive_reduction 1.19x, random_k_out 1.09x, random_tournament 1.02x.
SUBSTRATE-CAPPED (fnx<nx but native beats the delegated alternative -> kept, NOT reverted):
  gnmk 0.89x, projected_graph(dir) 0.64x, havel_hakimi 0.52x, configuration_model 0.42x.
  -> String-keyed MultiGraph storage (int-CSR migration br-r37-c1-yl606, Rust) +
     directed-projection Python-algo overhead. Not code-only-fixable.

CONCLUSION: the biggest clean wins are the redundant-conversion de-delegations (return
fnx directly, 4-5x). The MultiGraph-generator de-delegations are the only sub-1x group,
all substrate-bound and all still the best fnx option. No reverts warranted.
