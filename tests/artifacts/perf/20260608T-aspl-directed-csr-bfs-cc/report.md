# average_shortest_path_length (directed): integer-CSR BFS (br-r37-c1-wiener-csr sibling)

## Problem
The directed `average_shortest_path_length` kernel ran a per-source BFS over
`digraph.successors(name)` + `get_node_index(name)` (String hash per edge per
source). Already 1.75x faster than nx (nx directed all-pairs is also slow), but
left a large native gap.

## Lever (ONE)
Integer-CSR BFS via `successors_indices(u)` + reused dist/queue buffers. Witness
counts (edges_scanned/queue_peak/nodes_touched) stay byte-identical (same
successor order/length); BFS distances order-invariant -> avg byte-exact.

## Proof
- 50 random strongly-connected digraphs (incl self-loops): 0 mismatches.
- Golden sha256 == nx (`502fc53b...`).
- `pytest -k "average_shortest_path or shortest_path_length"`: 129 passed.

## Result (median-of-5)
| n, m       | nx        | fnx (after) | speedup vs nx |
|------------|-----------|-------------|---------------|
| 400, 3000  | 60.69 ms  | 3.15 ms     | 19.27x        |
| 800, 6000  | 265.94 ms | 14.00 ms    | 18.99x        |

Before: ~1.75x faster (0.57x ratio). After: ~19x faster than nx.
