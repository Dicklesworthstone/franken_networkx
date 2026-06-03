# post-bfs-capacity rejection residual sweep

Purpose: refresh the no-gaps target queue after `br-r37-c1-04z53.35` was
closed rejected with no source kept.

## Matching-hash residuals

- `bfs_tree`: fnx `0.006631971901515499s` vs NetworkX
  `0.004632352403132245s`, SHA
  `ef7bb62a7773a007f197d815a22d62d9b13b9347c4a662808e424387bb80aa5c`.
- `ego_graph_r2`: fnx `0.026285672295489348s` vs NetworkX
  `0.02217907609883696s`, SHA
  `4cb2bbd2f97df5ffee4f9db2762c3f74558efa2997debb50483bf6c2d49fc991`.

`dfs_edges` remained slower but had a mismatched SHA, so it was excluded as a
performance target until correctness is addressed.

## Selected next target

`ego_graph_r2` was selected for `br-r37-c1-04z53.36` because the BFS tree
construction surface already had several same-day rejected post-optimization
levers and the fresh ego profile still showed result-construction costs.
