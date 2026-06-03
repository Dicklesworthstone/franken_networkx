# ego_graph trusted raw edge batch recommendation

Bead: `br-r37-c1-04z53.41`

Target: `franken_networkx.ego_graph(G, 0, radius=2)` on
`barabasi_albert_graph(3000, 4, seed=42)`.

Profile evidence:
- Fresh post-quotient sweep:
  `tests/artifacts/perf/20260603T-post-kzo1b-reprofile/traversal_sweep.jsonl`.
- FNX mean `0.02576134620467201s`; NetworkX mean
  `0.02147259730263613s`; matching sweep SHA
  `4cb2bbd2f97df5ffee4f9db2762c3f74558efa2997debb50483bf6c2d49fc991`.
- Fresh baseline profile in this bead: `Graph.add_edges_from` wrapper cost
  `0.393s / 21 calls`; raw native add cost `0.228s / 21 calls`.

Alien primitive:
- Narrow drop-in boundary replacement.
- Vectorized/batched execution constants reduction.
- The public mutation membrane validates arbitrary user input. Inside
  `ego_graph`, the edge batch has already been constructed from valid graph
  edges after node-set filtering and attr-key gating, so the public validation
  wrapper is redundant at this internal boundary.

One lever:
- For non-multigraph `ego_graph` result construction only, call the module's
  captured raw `Graph/DiGraph.add_edges_from` method on the internally built
  `edges_to_add` list.
- Public `Graph.add_edges_from` and `DiGraph.add_edges_from` contracts are
  unchanged.

Expected value:
- Impact `2`: removes one Python validation layer from the current residual
  result-construction hotspot.
- Confidence `3`: profile points directly at the wrapper and the candidate
  keeps repeat-matched golden SHA.
- Effort `1`: one internal call-site change.
- Score: `2 * 3 / 1 = 6.0`, above the `2.0` keep bar.

Fallback:
- Restore `graph.add_edges_from(edges_to_add)` if golden SHA, focused ego parity,
  or confirmed hyperfine regresses.
