# bfs_tree indexed edge stream rejection proof

## Change
- Candidate: add an indexed native BFS edge stream and route the exact undirected `bfs_tree` fast path through it.
- Verdict: rejected and source reverted because the rch hyperfine gate regressed.

## Profile-backed target
- Bead: `br-r37-c1-04z53.22`
- Baseline fnx sample: mean `0.027893844101345166s`, p50 `0.02758266699675005s`.
- Baseline NetworkX sample: mean `0.005203583698312286s`, p50 `0.005254155999864452s`.
- Baseline hyperfine: `703.5 ms +/- 17.7 ms`.
- Profile top native call: `franken_networkx._fnx.bfs_tree` cumtime `0.150s` across 5 calls.

## Candidate result
- After fnx sample: mean `0.026949776998662855s`, p50 `0.026768455005367287s`.
- After hyperfine: `726.0 ms +/- 32.8 ms`.
- Gate: failed. Hyperfine after/before ratio `1.0321x` slower, so Score < 2.0.

## Isomorphism
- Ordering preserved: yes in the rejected candidate; it used the same queue order and `neighbors_indices` order as `bfs_edges`.
- Tie-breaking unchanged: yes in the rejected candidate; first discovery and CGSE decision order matched the existing traversal.
- Floating point: N/A.
- RNG seeds: unchanged.
- Golden outputs: baseline fnx, baseline NetworkX, and candidate fnx all produced `ef7bb62a7773a007f197d815a22d62d9b13b9347c4a662808e424387bb80aa5c` for repeat-10 normalized output.

## Final state
- No source change kept.
- `sha256sum -c tests/artifacts/perf/20260603T-bfs-tree-indexed-stream/artifact_sha256.txt` verifies the captured artifacts.
