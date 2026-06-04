# descendants_at_distance: local BFS instead of whole-graph native setup (br-r37-c1-dadlocal)

descendants_at_distance(source, k) returns the set of nodes at exactly distance k.
The native kernel pays an O(V+E) node-index / adjacency setup even for a LOCAL
small-k query, so it was 30-750x SLOWER than networkx for distance 1-2 (the common
k-hop-neighbourhood use): ~0.63ms (n=1500) / ~2.3ms (n=5000) for any k vs nx's
~0.01ms at k=1.

Lever (small-input setup tax, br-r37-c1-a0nl0): run networkx's exact layer BFS
directly on the fnx graph for the local case; if the frontier goes "global"
(visited > 64) the Rust BFS over the whole graph wins, so bail to the native
kernel. The result is a set (order-invariant) -> byte-identical to networkx and to
the native kernel; the bail path is the native kernel itself.

Proof: integer-distance parity vs networkx 0 mismatches over 120 graphs
(directed/undirected/string) x distances {0,1,2,3,5}; golden sha256; 61 existing
descendants tests pass. (A pre-existing non-integer-distance divergence -- int()
truncation vs nx's set() -- is unchanged and filed separately.)

| n | dist | nx (ms) | native (ms) | hybrid (ms) | vs nx | vs native |
|---|---|---|---|---|---|---|
| 1500 | 1 | 0.0092 | 0.623 | 0.0046 | 2.0x | 135x |
| 1500 | 2 | 0.0160 | 0.626 | 0.0225 | 0.71x | 28x |
| 1500 | 3 | 0.0402 | 0.629 | 0.0885 | 0.45x | 7x |
| 1500 | diam | 0.79 | 0.46 | 0.73 | 1.08x | 0.6x |
| 5000 | 1 | 0.0095 | 2.34 | 0.0031 | 3.1x | 749x |

before: distance 1-2 ~30-750x SLOWER than nx (whole-graph native setup).
after:  distance 1 ~2-3x FASTER than nx; distance 2 ~par; global distance bails to
        native (still faster than nx). Catastrophic small-k slowness eliminated.
        Residual at dist 2-3 = fnx G.neighbors PyO3 per-node overhead (substrate).
