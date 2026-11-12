# bfs_tree source add deferral rejection proof

Bead: `br-r37-c1-04z53.24`

## Profile-backed Target
- Residual sweep target: `bfs_tree(Graph, 0)` on BA(3000, 4, seed=42).
- Fresh baseline fnx repeat-10 mean: `0.02672410400118679s`.
- Fresh baseline NetworkX repeat-10 mean: `0.00556585960148368s`.
- Fresh repeat-10 digest: `ef7bb62a7773a007f197d815a22d62d9b13b9347c4a662808e424387bb80aa5c`.
- Operation-only cProfile baseline: 40 calls spent `1.056s` in native `_fnx.bfs_tree`.
- Hyperfine baseline: `725.2 ms +/- 15.0 ms`.

## Candidate Lever
Defer the returned tree's explicit `tree.inner.add_node(source)` until the BFS
edge list is empty. Non-empty trees would rely on
`extend_edges_unrecorded(edges)` to auto-create the source from the first BFS
edge.

## Candidate Result
- Candidate fnx repeat-10 mean: `0.03194493829942076s`.
- Candidate repeat-10 digest stayed `ef7bb62a7773a007f197d815a22d62d9b13b9347c4a662808e424387bb80aa5c`.
- Candidate operation-only cProfile: 40 calls spent `1.160s` in native `_fnx.bfs_tree`.
- Hyperfine after: `717.1 ms +/- 24.9 ms`.
- Restored repeat-5 digest after reverting: `8012caa5cb45d85c759859f3eab758979f275b08f93bae094ca8c25fba778301`.

## Isomorphism
- Ordering preserved in the rejected candidate: yes. The BFS edge stream still
  came from `fnx_algorithms::bfs_edges`; for non-empty trees the first edge
  auto-created the source before the first child, matching prior inner node
  order. Empty trees still explicitly inserted the source.
- Tie-breaking unchanged: yes. Neighbor traversal, visited marking, and
  first-discovery parent selection were untouched.
- Floating point: N/A.
- RNG seeds: unchanged. The benchmark graph seed is fixed; the library path is
  RNG-free.
- Golden output: baseline and candidate repeat-10 digests matched.

## Score and Verdict
- Impact 1: sampled mean regressed.
- Confidence 1: hyperfine intervals overlap and operation-only cProfile worsened.
- Effort 1: small local edit.
- Score: `1 * 1 / 1 = 1.0`.
- Verdict: rejected and reverted; no source code kept.
