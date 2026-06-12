# edge_boundary(data) — native pairs + to_dict_of_dicts live-dict lookup

## Lever
Last session de-delegated edge_boundary(data) to an in-process Python filter loop
over G[n] (~2.4-3.4x slower than nx — the Python iterate-filter floor). Now both
halves are native: the boundary (u, v) pairs come from the native edge_boundary
kernel (Rust filter, nx nbunch x adjacency order — byte-identical after the
br-r37-c1-tep7r sort fix); edge data is attached either trivially ({} / default
when graph_has_any_attrs proves no attrs) or via ONE native to_dict_of_dicts
snapshot ({u: {v: live_edge_dict}}, O(1) lookup per boundary edge).

## Correctness
edge_boundary vs nx across 768 cases (simple/directed/multi/multidi x nbunch2 x
data x default): 0 mismatches. golden sha 73cd8d2e67def25d. 115 boundary/cut_size/
volume tests pass. BONUS parity fix: data=True now yields the SAME LIVE edge dict
object nx does (the old in-process path returned a copy) — verified mutation
through the yielded dict propagates to the graph.

## Benchmark (warm min, interleaved before/after) — ratio = nx/fnx
| scenario                    | BEFORE fnx      | AFTER fnx       | self-speedup |
|-----------------------------|-----------------|-----------------|--------------|
| BA(200) attrless data=True  | 0.310ms (0.41x) | 0.088ms (1.47x) | 3.5x         |
| BA(500) attrless data=True  | 0.788ms (0.40x) | 0.244ms (1.32x) | 3.2x         |
| BA(500) attr data=weight    | 1.288ms (0.29x) | 0.320ms (1.21x) | 4.0x         |

Every edge_boundary(data) regime flips from slower-than-nx (0.29-0.41x) to
FASTER-than-nx (1.21-1.47x). Closes the residual from br-r37-c1-wpyzi.
