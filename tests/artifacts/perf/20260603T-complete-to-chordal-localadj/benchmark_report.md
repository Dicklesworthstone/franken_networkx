# complete_to_chordal_graph: kill O(|V|^2) subgraph-copy construction tax

Lever: the MCS-M minimal-fill-in inner test (is there a y->z path through
strictly-lower-weight nodes?) was implemented as
`has_path(H.subgraph(lower_nodes + [z, y]).copy(), y, z)`. The `.copy()` — added
because fnx's native `has_path` rejects filtered-view types — built a fresh
Graph (paying the full dual-rep construction tax) O(|V|^2) times. networkx runs
the identical MCS-M algorithm in ~0.64s because `G.subgraph(...)` is a
zero-copy VIEW; fnx's per-iteration copy made it ~77x slower.

`H` is unchanged during the loop (chords are applied only afterward), so
snapshot G's adjacency once into plain Python sets and run the reachability
test (BFS over the allowed node set) locally — no per-iteration graph
construction. `G.has_edge(y, z)` likewise becomes `z in adjacency[y]`.

## Benchmark (watts_strogatz(200, 6, 0.3), median of 3)

| impl                | time      |
|---------------------|-----------|
| nx                  | 674.9 ms  |
| fnx BEFORE          | 49,840 ms |
| fnx AFTER           | 196.1 ms  |

Self-speedup: ~254x (49.8s -> 0.196s). Gap vs nx: 77x-slower -> 0.29x
(3.4x FASTER than nx).

## Isomorphism + golden proof

Chordal completion H (edge set) and elimination ordering alpha byte-identical
to networkx across 5 random watts_strogatz graphs, an already-chordal tree
(identity, alpha all 0), and a complete graph; result verified chordal via
nx.is_chordal (test_complete_to_chordal_graph_native_parity, 4 cases incl. a
<10s perf guard). 396 existing chordal tests pass.

GOLDEN sha256 of {edges, nodes, alpha} (watts_strogatz(120, 6, 0.3, seed=99)):
bc34206b222837eac0885445... (nx == fnx).
