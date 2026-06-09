# perf(barycenter): integer-CSR all-pairs BFS

br-r37-c1-baryidx

## Problem
`fnx.barycenter` ran the lib.rs kernel `fnx_algorithms::barycenter`, which does a
String-keyed `HashMap<&str,usize>` BFS from every source (re-resolving neighbor
names + allocating a Vec per visit). At n=800 (tree) this was 91ms — the classic
"per-source BFS string tax" (cf reference_bfs_from_every_source_string_tax).

## Lever (one)
Replace the binding's kernel call with a local integer-CSR all-pairs BFS
(`barycenter_from_adjacency` over `graph_shortest_path_adjacency_indices`):
epoch-stamped visited array, integer distance sums per source, argmin tie-set in
ascending node-index order. Same node-iteration order + exact integer sums as
the kernel, so the result (and tie order) is byte-identical. No lib.rs change.

Touched: crates/fnx-python/src/algorithms.rs (binding + barycenter_from_adjacency).

## Proof (correctness)
66 connected graphs (path/cycle/complete/star/balanced+random trees/connected
gnp n=2..40): 0 mismatches vs nx (exact result-list order). Empty raises
NetworkXPointlessConcept; disconnected raises NetworkXNoPath. pytest -k
"barycenter or distance or center or periphery": 1398 passed.

## Timing (warm min, direct fnx)
| n   | fnx before | fnx after | self-speedup |
|-----|-----------:|----------:|-------------:|
| 200 |   5.35ms   |   0.27ms  |    ~20x      |
| 800 |  91.31ms   |   5.40ms  |    ~17x      |

NOTE on baseline: franken_networkx is registered as a NetworkX BACKEND in this
env, so `nx.barycenter(g)`'s inner `nx.shortest_path_length` dispatches to fnx's
fast all-pairs (reported ~1ms) — NOT a clean upstream baseline. Pure-upstream nx
all-pairs barycenter is ~178ms, so fnx-after (5.4ms) is ~33x faster than genuine
upstream. The honest, uncontaminated metric is the 17x self-speedup.

## Score
Impact: high (17x self-speedup, removes a String-keyed BFS hotspot). Confidence:
high (0/66, 1398 tests, unambiguous argmin algorithm). Effort: low. Score >> 2.0.
