# edge_load_centrality: integer-CSR BFS fast path

Lever: edge_load_centrality ran N per-source pure-Python Brandes-style BFS
(_edge_load_from_source_local -> _single_source_shortest_path_basic_local) plus
an O(E) (node, node)-keyed `between` dict rebuilt once per source. The
string/tuple-keyed dict churn over fnx adjacency made it 2-10x slower than nx
(up to 1.25s under host load). Relabel nodes to dense indices once, snapshot a
local integer adjacency list, and run all N BFS + the edge-load accumulation on
integer-keyed dicts.

PARITY: neighbor order (G[node]) and edge order (G.edges()) are preserved, so
the float accumulation is BIT-identical to the prior implementation (verified
`csr == current fnx` exactly across 3 seeds) and matches nx within 1e-9.

## Benchmark (watts_strogatz(200,6,0.3), median of 3)

| impl        | time    |
|-------------|---------|
| nx          | 156 ms  |
| fnx BEFORE  | 263 ms (steady) / 1246 ms (under load) |
| fnx AFTER   | 112 ms  |

Self-speedup ~2.3-11x depending on load; now 0.75x (FASTER than nx).

## Isomorphism proof

edge_load_centrality matches nx within 1e-9 across undirected/directed graphs,
cutoff in {1,2,3,False}, tiny graphs; both edge directions present; deterministic
(test_edge_load_centrality_csr_parity, 5 cases). Existing centrality conformance
tests pass.
