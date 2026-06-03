# Alien Recommendation Card: single_source_shortest_path indexed BFS

Bead: `br-r37-c1-04z53.10`

Profile target:
- `tests/artifacts/perf/20260603T-single-source-shortest-path-index/profile_baseline_fnx.txt`
- `single_source_shortest_path` on BA(3000, 4, seed=42), repeat=20.
- Native `_fnx.single_source_shortest_path` consumed 0.126 s cumulative before this pass.
- Baseline sampled mean: 0.008288126597472 s.
- NetworkX sampled mean: 0.0015962435980327427 s.

Primitive harvested:
- Alien graveyard 7.1/7.2: compact indexed/cache-local traversal state.
- Constants-kill-you discipline: replace string-key map growth and per-child path cloning with dense index vectors.

One lever:
- In `fnx-algorithms`, undirected `single_source_shortest_path` now traverses by node indices with `visited` and predecessor vectors, then reconstructs owned paths once in BFS discovery order.

Score:
- Impact 4: sampled native-call benchmark improved 4.498492067968333x.
- Confidence 3: golden output digest stayed identical and targeted Python parity tests passed.
- Effort 2: one Rust function plus proof artifacts.
- Opportunity score: 4 * 3 / 2 = 6.0. Keep.
