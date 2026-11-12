# perf(approximation.local_node_connectivity): in-process

br-r37-c1-x3c7v

## Problem
`fnx.approximation.local_node_connectivity` resolved through the
`_ApproximationNamespace.__getattr__` wrapper, which round-trips the graph via
`_networkx_graph_for_parity` (an **O(V+E)** faithful conversion) before running
White & Newman's greedy approximation. But that algorithm only touches the
**O(kappa)** augmenting-path nodes for a single source/target pair — so the
conversion dominated and the gap **SCALED with graph size**: 22.9× at n=400,
56× at n=800, 68× at n=1500 (the algorithm is ~0.2 ms; the conversion is
5–21 ms).

## Lever (one)
A concrete `local_node_connectivity` namespace method that runs the algorithm
**in-process** — no conversion. It reimplements nx's level-alternating
bidirectional BFS (`_bidirectional_pred_succ`) verbatim, reading neighbours via
the raw binding `_raw_neighbors_dispatch(G)` (so no `_networkx_graph_for_parity`
build AND no `G[v]` AtlasView per-access tax). The neighbour iteration order
matches G's adjacency, so the greedy path sequence — and the returned count — is
byte-identical to nx. Directed / multigraph / nx-private-storage graphs keep the
delegation path. Python-only.

## Proof (nx-exact)
`harness_proof.py`: 290 cases — gnp ×6 seeds × 3 sizes × 8 random (s,t) pairs ×
{cutoff None, 2}, plus octahedral graph (connectivity 4) and adjacent-node pairs.
**0 mismatches vs nx** on the returned integer. Same-node raises `NetworkXError`.
Golden sha256 (== nx):
`7c4979db57bc5a676115d2e15e7f75912194c0344c93af48cb673f4f470ef167`
pytest -k "node_connectivity/connectivity/approximation": **555 passed**.

## Timing (warm interleaved min-of-9, backend disabled, gnp(n,p), pair (0, n/2))
| n    | baseline fnx | nx       | baseline ratio | new fnx  | new ratio | self-speedup |
|------|-------------:|---------:|---------------:|---------:|----------:|-------------:|
| 400  |   4.995 ms   | 0.217 ms |    22.87×      | 0.264 ms |   1.22×   |   18.9×      |
| 800  |  11.529 ms   | 0.177 ms |    56.45×      | 0.229 ms |   1.30×   |   50.3×      |
| 1500 |  20.831 ms   | 0.248 ms |    68.43×      | 0.321 ms |   1.30×   |   64.9×      |

22–68× slower (SCALING with size) → 1.2–1.3× (flat), 18.9–64.9× self-speedup. The
size-dependent O(V+E) conversion is eliminated; the residual ~1.3× is the
raw-binding per-call overhead vs nx's native dict access.

## Score
Impact: high (kills a size-scaling 22–68× delegation tax on a connectivity
approximation; now ~parity, independent of graph size). Confidence: high
(byte-identical golden sha, 0/290 incl. octahedral/adjacent/cutoff, 555 tests).
Effort: moderate (faithful in-process BFS reimplementation, Python-only). Score
>> 2.0.
