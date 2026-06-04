# Directed Single-Target Length Native Reverse-BFS Proof

Beads: `br-r37-c1-a0nl0`, concrete target `br-r37-c1-cnndw`

## Change

Directed `single_target_shortest_path_length` now calls the existing native PyO3 reverse-BFS binding after the Python wrapper's target validation. The Rust directed helper returns discovery-order `(node, distance)` pairs instead of a `HashMap`, so PyO3 inserts Python dict keys in BFS order.

## Behavior

- Ordering preserved: yes. The old Python loop inserted `target`, then expanded BFS frontiers by iterating `G.predecessors(node)`. The Rust helper inserts `target`, expands the same frontier levels, and iterates `DiGraph.predecessors_iter(node)`, which is the same insertion-ordered predecessor `IndexSet` exposed by `G.predecessors(node)`.
- Tie-breaking preserved: yes. First discovery still wins. If multiple predecessors reach the same node at the same depth, the predecessor order is unchanged and later discoveries are ignored.
- Cutoff behavior preserved: yes. The public Python cutoff-normalization wrapper still runs before this function body; the raw binding receives the same normalized non-negative integer cutoff that the old Python loop would have used.
- Error behavior preserved: yes. Missing target is still checked in Python before the raw binding and raises the same `NodeNotFound` text.
- Floating-point: N/A. Hop counts are integers and no numeric accumulation occurs.
- RNG: N/A. No random state is read or written.
- Golden digest unchanged: `e6f4e822e915eb779243605c7de6c6185f141c64b15cc0bf444836f13db4df7c`.

## Score

- Impact: `4`
- Confidence: `5`
- Effort: `1`
- Score: `20.0`
- Verdict: PRODUCTIVE; keep.
