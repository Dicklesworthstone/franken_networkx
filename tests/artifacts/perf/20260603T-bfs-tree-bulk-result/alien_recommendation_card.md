# Alien Recommendation Card: BFS Tree Bulk Result Construction

## Symptom
`bfs_tree(Graph, 0)` remained the top traversal residual after sparse export
optimization. cProfile showed nearly all time inside native `_fnx.bfs_tree`.

## Graveyard Primitive
- Source: `/data/projects/alien_cs_graveyard/alien_cs_graveyard.md`
- Matched entries: profile-first optimization discipline, cache/locality
  constant-factor reduction, and batching to avoid repeated per-item
  bookkeeping when building a known-good artifact.

## Artifact-Coding Contract
- Runtime artifact: bulk directed BFS-tree result construction using the
  existing ordered BFS edge stream.
- Proof artifact: `isomorphism_proof.md`.
- Golden artifact: output digest in `baseline_fnx.jsonl`, `baseline_nx.jsonl`,
  and `after_fnx.jsonl`; artifact integrity in `artifact_sha256.txt`.
- Fallback policy: keep Python/NetworkX fallback for sorted-neighbor semantics
  and existing native exception fallbacks.

## EV Matrix
| Candidate | Impact | Confidence | Effort | Score |
|---|---:|---:|---:|---:|
| Bulk result construction for native `bfs_tree` | 2 | 5 | 1 | 10.0 |

## Decision
Ship. The lever is narrow, behavior-isomorphic, and both sampled timing and
hyperfine confirm a real win above the campaign threshold.
