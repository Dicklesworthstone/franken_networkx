# percolation_centrality: integer-CSR BFS fast path (unweighted)

Lever: the unweighted percolation centrality ran N per-source Brandes BFS via
`_single_source_shortest_path_basic_local` — pure-Python BFS over string-keyed
dicts (`predecessors`, `sigma`, `distances`) walking fnx adjacency once per
node (the "BFS-from-every-source string tax"), ~3x slower than nx. Relabel
nodes to dense indices once, snapshot a local integer adjacency list, and run
all N BFS + Brandes accumulation on flat integer arrays. weight != None and
graphs with <=2 nodes keep the original path.

PARITY: Brandes accumulation is order-independent and neighbor order is
preserved from `G[node]`, so the float accumulation is BIT-IDENTICAL to the
previous dict implementation (verified `csr == current fnx` exactly in the
prototype across 3 seeds) and matches networkx within 1e-12 (the pre-existing
fnx-vs-nx ULP tolerance; not a regression).

## Benchmark (watts_strogatz(200,6,0.3), percolation states, median of 5)

| impl        | time     |
|-------------|----------|
| nx          | 56.2 ms  |
| fnx BEFORE  | 173.4 ms |
| fnx AFTER   | 32.9 ms  |

Self-speedup ~5.3x; gap 3.2x-slower -> 0.61x (1.6x FASTER than nx).

## Isomorphism proof

percolation_centrality matches networkx within 1e-12 across undirected/directed
x attributed/default-state graphs, custom states dict, default attribute=1, and
the weighted (Dijkstra) path (unchanged); bit-identical to the prior fnx output
(test_percolation_centrality_csr_parity, 5 cases). Existing centrality
conformance test passes.
