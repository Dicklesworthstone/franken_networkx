# Rejected Lever: bfs_tree redundant child existence probe

Bead: `br-r37-c1-ekjvd`

Profile target:
- Current release traversal sweep: `tests/artifacts/perf/20260603T-next-residual-sweep/traversal_sweep_head_release.jsonl`.
- `bfs_tree` on BA(3000, 4, seed=42), repeat=5.
- Baseline fnx mean: 0.03685493959637824 s.
- Baseline NetworkX mean: 0.005177216001902707 s.
- Baseline fnx / NetworkX ratio: 7.1186791477955484.
- Baseline digest: `8012caa5cb45d85c759859f3eab758979f275b08f93bae094ca8c25fba778301`.
- cProfile repeat-5: native `_fnx.bfs_tree` consumed 0.214 s of 0.214 s.

Candidate lever:
- Removed the explicit `tree.inner.has_node(v)` guard while constructing the result DiGraph, relying on the invariant that BFS tree edges discover each child exactly once.

Behavior proof:
- Ordering: BFS edge order was unchanged because the edge list still came from `fnx_algorithms::bfs_edges`.
- Tie-breaking: no neighbor traversal policy changed.
- Floating point: none.
- RNG: none in the library path; benchmark graph seed was fixed at 42.
- Golden output: candidate digest stayed `8012caa5cb45d85c759859f3eab758979f275b08f93bae094ca8c25fba778301`.

Benchmark results:
- Focused candidate sample mean: 0.03532499599969015 s.
- Focused sample speedup: 1.0433152364019237x.
- Baseline hyperfine mean: 0.8152559647628573 s.
- Candidate hyperfine mean: 0.8298784600885716 s.
- Hyperfine mean ratio: 0.9823802883634177x, a regression.
- Baseline hyperfine median: 0.8159525486200001 s.
- Candidate hyperfine median: 0.8084855526600001 s.

Score:
- Impact 1: focused sample improved slightly, but process-level mean regressed.
- Confidence 1: hyperfine did not confirm a real win.
- Effort 1: one branch removal.
- Opportunity score: 1 * 1 / 1 = 1.0. Reject.

Verdict:
- Rejected. The `bfs_tree` code change was manually removed.
- Release extension was rebuilt after removal so subsequent profiling uses the kept implementation.
- Targeted traversal parity after restoration: `21 passed, 118 deselected`.
- UBS on Markdown/text proof artifacts exited 0 with no recognizable source languages.
