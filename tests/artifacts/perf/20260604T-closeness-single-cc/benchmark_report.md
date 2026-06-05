# closeness_centrality(u=single): single-source BFS instead of delegate (br-r37-c1-clsingle)

closeness_centrality(G, u=node) -- a single-node request on the standard
unweighted / wf_improved / undirected path -- delegated to networkx, which paid a
full fnx->nx graph conversion (O(V+E)) just to run ONE BFS. For one node on n=1500
that was ~11.5 ms vs networkx's ~0.48 ms (~25x SLOWER, hidden by the
default-all-nodes benchmark which uses the fast Rust kernel).

Lever (small-input conversion-tax class, br-r37-c1-a0nl0): compute the single BFS
from u directly via single_source_shortest_path_length, then nx's exact formula
`(|reach|-1)/totsp * (|reach|-1)/(n-1)`. The total path length is a sum of INTEGER
hop counts, so the result is byte-identical to networkx AND to
_raw_closeness_centrality[u]. Gated to undirected, unweighted (distance is None),
wf_improved, u in G; directed / weighted / non-wf / missing-u still delegate.

Proof: EXACT equality vs networkx 983/983 (and == the full-dict value) across int /
string / disconnected graphs; golden sha256 over single-node closeness on a
100-graph corpus (0 mismatches); 110 existing closeness tests pass.

| n | nx (ms) | fnx before | fnx after | speedup |
|---|---|---|---|---|
| 400 | 0.108 | ~3.0 (delegate) | 0.042 | 2.54x |
| 1500 | 0.478 | ~11.5 (delegate) | 0.182 | 2.63x |
| 4000 | 1.300 | ~ (delegate) | 0.514 | 2.53x |

before: ~25x SLOWER (whole-graph fnx->nx conversion for one BFS).
after:  2.5-2.6x FASTER than networkx.
