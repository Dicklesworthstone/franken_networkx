# bfs_tree edge metadata key-move rejection proof

Bead: `br-r37-c1-aimv1`

Profile-backed target:
- Fresh fallback sweep: `tests/artifacts/perf/20260603T-fallback-residual-sweep/traversal_sweep.jsonl`.
- `bfs_tree` on BA(3000, 4, seed=42).
- Sweep fnx mean: `0.028452350199222563s`.
- Sweep NetworkX mean: `0.003979585997876711s`.
- Sweep digest: `8012caa5cb45d85c759859f3eab758979f275b08f93bae094ca8c25fba778301`.

Baseline for this lever:
- Focused fnx repeat-10 mean: `0.02688470220164163s`.
- NetworkX repeat-10 mean: `0.005465391201141756s`.
- Focused repeat-10 digest: `ef7bb62a7773a007f197d815a22d62d9b13b9347c4a662808e424387bb80aa5c`.
- Hyperfine baseline: `721.8 ms +/- 17.0 ms`.

Candidate lever:
- Inserted `tree.inner` edges from borrowed edge refs before result metadata construction.
- Consumed the owned BFS edge vector into `edge_py_attrs` so edge metadata keys moved existing `String`s instead of cloning `(u, v)`.

Candidate result:
- Focused fnx repeat-10 mean: `0.027562860399484634s`.
- Focused digest stayed `ef7bb62a7773a007f197d815a22d62d9b13b9347c4a662808e424387bb80aa5c`.
- Hyperfine after: `774.0 ms +/- 24.6 ms`.
- Restored repeat-5 digest after reverting: `8012caa5cb45d85c759859f3eab758979f275b08f93bae094ca8c25fba778301`.

Isomorphism proof:
- Ordering: candidate traversal still used the same `fnx_algorithms::bfs_edges` result, and `extend_edges_unrecorded` received edges in the same order.
- Tie-breaking: no neighbor traversal, visited marking, or first-discovery parent selection changed.
- Floating point: none on this path.
- RNG: none in the library path; benchmark graph seed fixed to `42`.
- Golden output: focused repeat-10 digest was unchanged.

Score and verdict:
- Impact 1: clone removal was plausible but sample mean regressed.
- Confidence 1: hyperfine confirmed a process-level regression.
- Effort 1: small local edit.
- Score: `1 * 1 / 1 = 1.0`.
- Verdict: rejected and reverted; no source code kept.
