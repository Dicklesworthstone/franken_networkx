# Alien Recommendation Card: bfs_tree source add deferral

## Symptom
`bfs_tree(Graph, 0)` remains a traversal residual on BA(3000, 4, seed=42).
The operation-only cProfile baseline shows 40 calls spending 1.056 s in native
`_fnx.bfs_tree`.

## Graveyard Primitive
- Source: `/data/projects/alien_cs_graveyard/alien_cs_graveyard.md`
- Source: `/data/projects/alien_cs_graveyard/high_level_summary_of_frankensuite_planned_and_implemented_features_and_concepts.md`
- Matched primitive: profile-first constant-factor reduction by removing
  redundant bookkeeping from a hot artifact-construction path.

## Artifact-Coding Contract
- Runtime artifact: defer explicit source-node insertion in the returned
  `PyDiGraph` unless the BFS tree has no edges.
- Proof artifact: `isomorphism_proof.md`.
- Golden artifact: repeat-10 digest in `baseline_fnx.jsonl`,
  `baseline_nx.jsonl`, and `after_fnx.jsonl`; restored repeat-5 digest in
  `restored_fnx.jsonl`.
- Fallback policy: reject and restore source if sampled timing or hyperfine
  fails to prove a real win.

## EV Matrix
| Candidate | Impact | Confidence | Effort | Score |
|---|---:|---:|---:|---:|
| Defer explicit source inner add on non-empty BFS trees | 1 | 1 | 1 | 1.0 |

## Decision
Reject. Golden output stayed unchanged, but focused samples regressed and
hyperfine moved only within overlapping noise.
