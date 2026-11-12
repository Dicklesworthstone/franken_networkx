# Alien Artifact Coding Card

Source directive: apply no-gaps optimization only to profile-backed hotspots, one lever per pass, and keep only changes with Score at least 2.0.

Imported primitive idea: closed-loop specialization. When an internal copy loop owns both the iteration contract and the insertion target, remove redundant public observer checks and amortize insertion through a bulk path while preserving the public contract at the boundary.

Application: `ego_graph` simple-Graph edge copy in `python/franken_networkx/__init__.py`.

Evidence: baseline profile showed `ego_graph` at `0.574s` cumulative over 9 calls, with public edge iteration and repeated `Graph.add_edge` dominating. The closed-copy fast path reduced profile time to `0.425s`, kept the golden digest unchanged, improved repeat-21 mean to `0.04233674376224544s`, and improved hyperfine from `577.3 ms +/- 59.0 ms` to `508.7 ms +/- 21.2 ms` with a 20-run candidate check at `526.5 ms +/- 25.6 ms`.

Decision: keep. Next residual should reprofile after this commit; remaining visible costs are `add_edges_from`, `_materialize`, node insertion, and BFS node-set construction.
