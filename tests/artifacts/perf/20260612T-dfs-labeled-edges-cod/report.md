# br-r37-c1-q60fc rejected lever: native event-list dfs_labeled_edges

Target: `dfs_labeled_edges` on `watts_strogatz_graph(200, 6, 0.17, seed=20260612)`, filed as 2.7x slower than NetworkX because the Python implementation resumes a `G.neighbors(child)` iterator through PyO3 for every discovered node.

Lever tested: a native Rust DFS event stream that emitted NetworkX labels (`forward`, `nontree`, `reverse`, `reverse-depth_limit`) and a PyO3 wrapper that reconstructed Python display objects before the public generator yielded triples.

Behavior proof:

- Golden digest before and after: `d78d98420cf41910c088ffad8ff50d74935de63b3b22c775a4ef7a32ba74b9ad`.
- Fixtures: undirected WS200, directed WS200, depth_limit=3, source=17.
- All fixtures matched NetworkX exactly; event counts and per-case digests were unchanged.
- Ordering/tie-breaking: traversal event order was byte-identical in the proof payload.
- Floating-point/RNG: traversal output has no FP surface; RNG was only deterministic fixture construction.

Benchmark result:

- WS200 direct mean: `0.000326843677s` baseline -> `0.000379434700s` after (`0.86x`, regression).
- Directed WS200 direct mean: `0.000337440332s` baseline -> `0.000264265825s` after (`1.28x`, not the filed undirected target).
- Process hyperfine mean: `0.417962619s` baseline -> `0.397202139s` after (`1.05x`).
- cProfile WS200, 200 calls: `0.235s` baseline -> `0.111s` after, but direct-call evidence on the filed target regressed.

Decision: rejected. No production code kept. Score: `0` for the filed undirected target because direct-call impact was negative and process-level impact was below the keep threshold.

Next route: avoid the native event-list/PyObject-list shape. The deeper primitive should be an exact-int/display-certified lazy iterator or no-intermediate-list traversal path that preserves NetworkX generator timing and row-key discovery semantics while avoiding per-event Python tuple materialization upfront.
