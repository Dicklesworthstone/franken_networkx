# bfs_edges Vec preallocation rejection proof

Bead: br-r37-c1-04z53.31

Target:
- `bfs_tree(Graph, 0)` on BA(3000, 4, seed=42).
- Current residual gap before edit: FNX `0.006757828120607883s`, NetworkX `0.004501300221891142s`.

Candidate lever:
- Preallocate the `Vec<(String, String)>` returned by the three native BFS edge producers with the node-count upper bound.
- No traversal logic, queue behavior, visited marking, depth-limit handling, graph mutation, floating-point arithmetic, or RNG use changed.

Behavior proof:
- Ordering/tie-breaking: unchanged. Neighbor iteration order and queue push/pop order were not modified.
- Source/depth behavior: unchanged. Source validation, `depth_limit`, and empty-result paths were not modified.
- Floating point: N/A.
- RNG: N/A.
- Golden output SHA: `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64` before, after, and NetworkX.

Result:
- Rejected. Direct rch sample regressed from `0.006757828120607883s` to `0.006814447081414983s`.
- Hyperfine improved only `0.6238517696533332s` to `0.6064132063333333s` (1.0288x), too small and noisy to meet Score >= 2.0.
- Source restored to pre-candidate state.
