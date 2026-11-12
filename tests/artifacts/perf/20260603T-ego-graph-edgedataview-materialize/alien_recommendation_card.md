# Alien Artifact Coding Card

Source directive: apply no-gaps optimization only to profile-backed hotspots and keep one lever only when the measured score is at least 2.0.

Imported primitive idea: avoid redundant observer/fail-fast checks in a closed internal copy loop by reusing the already-materialized edge sequence. This follows the safe specialization pattern: narrow dynamic type guard, same iteration source, no external callback, no ordering change.

Application: `ego_graph` simple-Graph edge copy in `python/franken_networkx/__init__.py`.

Evidence: the candidate removed `_FailFastEdgeIterator.__next__` from the focused profile, but repeat samples regressed from `0.04495093485664776s` to `0.052583811141500646s` and repeat-21 stayed at `0.05161768471242838s`. Hyperfine did not establish a stable process-level win.

Decision: reject and revert. The next profile-backed primitive should target `Graph.add_edge` batch insertion or a native ego-subgraph copy path, because after the fail-fast bypass profile the dominant residual was edge insertion itself.
