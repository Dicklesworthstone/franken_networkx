# link prediction: drop fnx->nx conversion, compute on fnx graph (br-r37-c1-lpconv)

jaccard_coefficient / adamic_adar_index / resource_allocation_index /
preferential_attachment all DELEGATED to networkx, which performed a full
fnx->nx graph conversion (O(V+E)) on EVERY call regardless of ebunch size. So
scoring a handful of candidate pairs (the common real use) paid the whole-graph
conversion: ~114 ms at n=2000 vs networkx's ~0.03 ms -- ~4000x SLOWER. The
default all-non-edges path was also ~0.94x (conversion + nx Python compute).

Lever: reproduce networkx's exact algorithm directly on the fnx graph -- no
conversion. Pair order = nx's non_edges (nodes.pop() + nodes - N(u) over CPython
sets); common neighbours iterate G.neighbors(u) (nx's G[u] order) filtered by
N(v) membership and w not in (u,v); scores use builtin sum (same compensated
summation as nx) so floats are byte-identical and the empty sum is int 0.
Adjacency sets / degrees are memoized lazily, so a small ebunch only touches its
endpoints.

Proof: EXACT tuple-list equality (f == n) vs networkx 400/400 across default +
explicit ebunch, int / string / self-loop graphs; golden sha256 over the four
functions on an 80-graph corpus; 308 existing link-prediction tests pass.

Small ebunch (10 pairs), the common use case:
| n | metric | nx (ms) | fnx before | fnx after |
|---|---|---|---|---|
| 500 | resource_allocation | 0.016 | ~6.0 | 0.036 |
| 2000 | resource_allocation | 0.028 | ~114 | 0.086 |
| 2000 | adamic_adar | 0.029 | ~114 | 0.086 |

before: small ebunch ~300x-4700x SLOWER (whole-graph conversion).
after:  small ebunch within ~0.03-0.09 ms (the conversion catastrophe is gone);
        default all-non-edges 0.94x -> 1.97x FASTER.
