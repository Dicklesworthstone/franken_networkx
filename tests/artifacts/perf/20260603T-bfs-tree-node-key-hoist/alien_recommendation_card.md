# Alien Recommendation Card: BFS tree node-key lookup hoist

## Target
- Bead: `br-r37-c1-04z53.44`
- Workload: `bfs_tree` on BA(3000, 4, seed=42)
- Baseline residual: FNX `0.007188971197319915s`, NetworkX `0.004845346014553798s`
- Profile evidence: rch cProfile repeat=80 put `0.583s` cumulative in native `_fnx.bfs_tree`

## Candidate Primitive
- Graveyard family: cache-aware boundary hoist / map lookup locality
- Artifact family: certified rewrite with explicit non-regression obligations
- Lever: hoist the source `node_key_map` once in `bfs_tree` result construction and replace repeated `GraphRef::py_node_key` dispatch with an equivalent direct map lookup plus canonical-string fallback.

## Score Before Edit
- Impact: 2
- Confidence: 3
- Effort: 1
- Score: `2 * 3 / 1 = 6.0`

## Fallback Trigger
Reject if either direct mean or hyperfine mean fails to improve while preserving the golden SHA.

## Verdict
Rejected. The golden SHA stayed unchanged, but direct FNX mean regressed and hyperfine did not improve. Source was restored before closeout.
