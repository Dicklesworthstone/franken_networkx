# bfs_tree lazy edge metadata benchmark report

Bead: `br-r37-c1-bdd87`

Baseline:
- FNX direct mean: `0.07658544930018252s`.
- FNX direct p50: `0.07398850850586314s`.
- NetworkX direct mean: `0.018295269904774612s`.
- NetworkX direct p50: `0.014852798994979821s`.
- Hyperfine mean: `0.7552698227200002s`.
- cProfile native `_fnx.bfs_tree`: `1.185s` over 20 calls.

Candidate:
- FNX direct mean: `0.07933432019199245s`.
- FNX direct p50: `0.07713596848770976s`.
- NetworkX direct mean: `0.01954261744976975s`.
- NetworkX direct p50: `0.014732907497091219s`.
- Hyperfine mean: `0.7815417369066665s`.
- cProfile native `_fnx.bfs_tree`: `1.180s` over 20 calls.

Restored source:
- FNX direct mean: `0.07885979484854033s`.
- FNX direct p50: `0.07708135999564547s`.

Score:
- Impact: `0` because direct and hyperfine both regressed.
- Confidence: `4` because golden SHA and focused behavior proof passed.
- Effort: `2`.
- Score: `0 * 4 / 2 = 0.0`.

Decision:
- Rejected and source restored. The attempted representation change did not move the dominant native `_fnx.bfs_tree` cost enough to offset accessor/conversion overhead.
