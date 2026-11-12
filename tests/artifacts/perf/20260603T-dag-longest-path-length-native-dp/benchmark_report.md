# br-r37-c1-6cxvz: rejected dag_longest_path_length direct DP

## Target

- Bead: `br-r37-c1-6cxvz`
- Fixture: deterministic 400-node DiGraph DAG, edge probability `0.02`, seed `20260603`
- Operation: `dag_longest_path_length(G)` only
- Profile-backed hotspot: post-`br-r37-c1-pzutt` profile showed `dag_longest_path_length` calling `dag_longest_path`, so the length API reran the native predecessor DP.

## Baseline

- FNX direct rch timing: `0.3862517800007481s / 300` = `0.001287505933335827s` per call
- NetworkX oracle rch timing: `0.2931383049872238s / 300` = `0.000977127683290746s` per call
- Hyperfine baseline via rch, 120 repeats: `458.0 ms +/- 26.5 ms`
- Golden SHA: `34f3f915ca217ba76be7da282e59e7c1eddf322628c011cb634db0c7b0c4b4fb`

## Candidate

Add an exact-`DiGraph` `dag_longest_path_length` path that computes the DP length directly from `_native_in_edges_data_key` instead of calling `dag_longest_path` and summing the resulting path.

## Result

- Candidate direct rch timing: `0.3712657589931041s / 300` = `0.0012375525299770137s` per call (`1.04x`)
- Candidate hyperfine via rch: `436.5 ms +/- 26.8 ms` (`1.05x`, overlapping variance)
- Restored direct rch timing: `0.384773498022696s / 300` = `0.00128257832674232s` per call
- Golden SHA stayed unchanged.

Score: Impact `1.05` x Confidence `1` / Effort `1` = `1.05`; reject.

## Next Deeper Target

The rejected micro-lever confirms the remaining DAG length gap is not the path-sum tail. The next target should replace the duplicated topological/in-edge snapshot surface with a fused topological-DP primitive: one native pass over the DAG that emits either path or length while preserving NetworkX's predecessor-order stable tie-break.

