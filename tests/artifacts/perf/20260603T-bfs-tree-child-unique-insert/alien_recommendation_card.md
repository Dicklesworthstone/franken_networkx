# bfs_tree child-unique insertion recommendation

Bead: `br-r37-c1-04z53.42`

Target: `franken_networkx.bfs_tree(Graph, 0)` on
`barabasi_albert_graph(3000, 4, seed=42)`.

Profile evidence:
- Post-ego reprofile:
  `tests/artifacts/perf/20260603T-post-ego-raw-edge-batch-reprofile/traversal_sweep.jsonl`.
- FNX mean `0.0073860224016243595s`; NetworkX mean
  `0.005070463704760187s`; matching SHA
  `ef7bb62a7773a007f197d815a22d62d9b13b9347c4a662808e424387bb80aa5c`.
- Baseline cProfile in this bead: native `_fnx.bfs_tree` consumed
  `0.365s / 50 calls`.

Alien primitive:
- Proof-carrying narrow invariant at an internal representation boundary.
- The BFS tree edge stream has one incoming tree edge for each discovered child.
  That invariant lets result construction skip a per-edge `HashMap` membership
  check before inserting child metadata.

One lever:
- In `_fnx.bfs_tree` result construction, insert each child node metadata record
  directly from the BFS tree edge stream instead of checking
  `node_key_map.contains_key(v)` first.
- Traversal, edge stream generation, source insertion, and edge attr creation
  are unchanged.

Expected value:
- Impact `2`: removes one hash lookup per BFS tree edge from the current native
  hotspot.
- Confidence `2`: direct operation sample, cProfile, and first hyperfine moved
  the same direction; process confirm remained lower but close to noise.
- Effort `1`: one local Rust result-construction edit.
- Score: `2 * 2 / 1 = 4.0`, above the `2.0` keep bar.

Fallback:
- Restore the `contains_key` guard if duplicate-child behavior is observed,
  golden SHA changes, focused BFS parity fails, or process timings regress.
