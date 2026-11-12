# single_target_shortest_path_length: route undirected to native single_source (br-r37-c1-sptlen)

single_target_shortest_path_length(G, target) returns {source: distance} -- a full
reverse BFS to target. It was a per-node Python BFS (_single_target_shortest_path_
neighbors per node, PyO3 overhead x V) -> ~6x SLOWER than networkx.

Lever: for UNDIRECTED graphs the distance from every node TO target equals the
distance FROM target (symmetric), so route to the native single_source kernel
(which is already ~2.5x faster than networkx) instead of the Python reverse-BFS.
Hop counts are integers and both build the dict in BFS-from-target order, so the
result is byte-identical (value + key order). Directed graphs need reverse
adjacency, so they keep the Python path (unchanged).

Proof: parity vs networkx 0 mismatches over 120 graphs (directed/undirected/string)
x cutoffs {None,1,2,3} -- value AND dict key order; golden sha256; 23 existing
single_target tests pass.

| n | nx (ms) | fnx before | fnx after | speedup |
|---|---|---|---|---|
| 400 | 0.156 | 0.914 | 0.067 | 2.34x |
| 1500 | 0.707 | 3.885 | 0.277 | 2.55x |
| 4000 | 1.944 | (Python BFS) | 0.767 | 2.53x |

before: undirected ~6x SLOWER than nx (per-node Python reverse BFS).
after:  undirected 2.3-2.6x FASTER than nx. Directed unchanged (~6x slower, the
        reverse-BFS PyO3-per-node tax -- needs a native reverse-BFS kernel).
