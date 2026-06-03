# Alien Artifact Coding Card

Source directive: apply no-gaps optimization only to profile-backed hotspots, one lever per pass, and keep only changes with Score at least 2.0.

Imported primitive idea: amortize repeated per-item insertion overhead by batching a closed internal copy loop into a single bulk insertion call while preserving input order.

Application: `ego_graph` simple-Graph edge copy in `python/franken_networkx/__init__.py`.

Evidence: baseline profile showed repeated `Graph.add_edge` at `0.229s` cumulative for 9 calls. The candidate changed the profile shape slightly, but repeat-9 timing regressed from `0.04547556122027648s` to `0.045938352554609686s`, repeat-21 stayed at `0.04591676633225732s`, and hyperfine remained flat at `534.9 ms +/- 17.6 ms` vs `534.7 ms +/- 19.3 ms`.

Decision: reject and revert. The next profile-backed primitive should avoid the public EdgeDataView and add_edge surfaces together, likely via a dedicated native ego-subgraph copy path that preserves NetworkX edge orientation and attr semantics.
