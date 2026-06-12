# community.is_partition / partition_quality — concrete in-process overrides

## Lever
fnx.community does `from networkx.algorithms.community import *`, so these were
nx's @nx._dispatchable versions -> calling on an fnx graph round-tripped the WHOLE
graph through _fnx_to_nx (full O(V+E) conversion) per call: is_partition (an O(V)
membership check) 52x slower, partition_quality 14x. Added concrete overrides
running nx's EXACT algorithms in-process. is_partition also snapshots set(G) once
so per-element membership is a pure-Python set lookup (not a PyO3 `n in G`
crossing) -- this is what pushes it past nx.

## Correctness
120 cases (Graph/DiGraph/MultiGraph x partitions {valid,single,missing,overlap}):
is_partition bool + partition_quality (coverage,performance) floats + the exact
NetworkXError message on invalid partitions -- all identical to nx, 0 mismatches.
golden 30f881fc. 353 community tests pass.

## Benchmark (warm min, interleaved before/after) -- ratio nx/fnx
| op               | BEFORE(trapped) | AFTER    | self-speedup | vs nx        |
|------------------|-----------------|----------|--------------|--------------|
| is_partition     | 0.9459ms        | 0.0084ms | 112x         | 2.0x FASTER  |
| partition_quality| 2.3085ms        | 0.1595ms | 14.5x        | 0.77x (edge-loop floor) |

is_partition flips 52x slower -> 2x FASTER than nx. partition_quality's residual
1.3x is the `for e in G.edges()` PyO3 iteration (nx walks pure-Python dicts).
