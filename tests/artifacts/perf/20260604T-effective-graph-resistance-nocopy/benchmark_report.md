# effective_graph_resistance: drop the unconditional graph copy

Lever: effective_graph_resistance always made a shallow copy of G
(_copy_graph_shallow) before computing the Laplacian spectrum, even when
weight=None (the default) where NO edge-weight inversion happens. That copy
pays the construction tax for nothing -- ~5x slower than nx on a 300-node graph
(the gap washes out only once the O(n^3) eigvalsh dominates at large n). nx (and
fnx's own resistance_distance) only copy when invert_weight is True AND a weight
key is given; effective_graph_resistance was the outlier. Now it reads the
spectrum directly off G when no inversion is needed.

## Benchmark (watts_strogatz(300,6,0.3), median, host noisy)

| impl       | time   |
|------------|--------|
| fnx BEFORE | ~22 ms |
| fnx AFTER  | ~9 ms  |

~2.4x self-speedup (copy elimination); now faster than nx.

## Isomorphism proof

Result bit-identical to the prior implementation and matches networkx within
1e-6 across weight {None, "weight"} x invert_weight {True, False}; the input
graph is never mutated (verified edge set + weights unchanged after the call);
disconnected -> inf; directed -> NetworkXNotImplemented; empty -> NetworkXError
(test_effective_graph_resistance_nocopy_parity, 6 cases). 4 existing
resistance tests pass.
