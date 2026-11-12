# ego_graph empty node attrs rejection proof

Bead: br-r37-c1-04z53.32

Target:
- `ego_graph(Graph, 0, radius=2)` on BA(3000, 4, seed=42).
- Baseline FNX `0.0242919315972055s`; NetworkX `0.021780150699972484s`.

Candidate lever:
- In the ego_graph node-copy loop, skip `dict(G.nodes[node])` and `**{}` when node attrs are empty.
- Non-empty attrs continued through the existing `dict(...)` plus keyword-splat path.

Behavior proof:
- Node order: unchanged. The same `ordered_nodes` list drove the loop.
- Edge order/tie-breaking: unchanged. The edge-copy path was not modified.
- Center removal, weighted/directed branches: unchanged.
- Floating point: N/A for this unweighted path.
- RNG: N/A.
- Golden output SHA: `5dc8ab88ec0fd5490369d69f379aafc838d027576d99d986772bd178131888e3` before, after, and NetworkX.

Result:
- Rejected. Direct rch sample regressed from `0.0242919315972055s` to `0.02533302050239096s`.
- Hyperfine moved from `0.6794944671333334s` to `0.6558192539333335s` (1.0361x), too small/noisy to meet Score >= 2.0.
- Source restored to pre-candidate state.
