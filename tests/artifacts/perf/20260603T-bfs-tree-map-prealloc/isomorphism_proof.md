# bfs_tree result-map preallocation rejection proof

## Change
- Candidate: reserve `node_key_map`, `node_py_attrs`, and `edge_py_attrs` capacity for the returned `PyDiGraph` from the already-known BFS edge count.
- Verdict: rejected and source reverted because the benchmark result was not a real win.

## Profile-backed target
- Bead: `br-r37-c1-04z53.23`
- Target-selection sweep: `tests/artifacts/perf/20260603T-bfs-tree-map-prealloc/target_selection_sweep.jsonl`
- Current sweep kept `bfs_tree` as the largest absolute traversal gap: fnx mean `0.027995695199933834s` vs NetworkX mean `0.003996903399820439s`.
- Baseline fnx repeat-10 sample: mean `0.026950324898643886s`, p50 `0.026484039990464225s`.
- Baseline NetworkX repeat-10 sample: mean `0.004527073499048129s`, p50 `0.004415625997353345s`.
- Baseline hyperfine: `737.1 ms +/- 18.2 ms`.

## Candidate result
- After fnx repeat-10 sample: mean `0.02773389009817038s`, p50 `0.02750242900219746s`.
- After hyperfine: `722.4 ms +/- 29.5 ms`.
- Gate: failed. The sample regressed and the hyperfine intervals overlap, so the candidate did not prove a real win despite a lower hyperfine mean.

## Isomorphism
- Ordering preserved: yes in the rejected candidate; traversal and insertion order remained unchanged.
- Tie-breaking unchanged: yes; `fnx_algorithms::bfs_edges` was still the source of BFS parents and ordering.
- Floating point: N/A.
- RNG seeds: unchanged.
- Golden outputs: baseline fnx, baseline NetworkX, and candidate fnx all produced `ef7bb62a7773a007f197d815a22d62d9b13b9347c4a662808e424387bb80aa5c` for repeat-10 normalized output.

## Final state
- No source change kept.
- `sha256sum -c tests/artifacts/perf/20260603T-bfs-tree-map-prealloc/artifact_sha256.txt` verifies the captured artifacts.
