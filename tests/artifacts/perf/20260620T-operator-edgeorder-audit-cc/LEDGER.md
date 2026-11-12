# Verification audit (code-only) — operator/constructor edge-order byte-exactness (br-r37-c1-edgeorderaudit)

- Agent: `BlackThrush` · 2026-06-20 · DISK-LOW: code-only, NO cargo. Verified with existing install.

Closes the set-iteration-order edge-ORDER bug class (the same class as the bipartite
projection fixes and the standalone-intersection fix br-r37-c1-interorder shipped the
prior commit). Swept every Python operator/constructor that builds an edge set, checking
EXACT list(R.edges()) order (not sorted) vs nx-on-an-nx-graph over thousands of random
inputs:

| function                | cases   | exact-order vs nx |
|-------------------------|---------|-------------------|
| intersection (Graph)    | 6000    | 6000/6000 (FIXED last commit; was ~0.2% divergent) |
| intersection_all        | 3000    | 3000/3000 |
| union (disjoint)        | 4000    | 4000/4000 |
| compose                 | 3000    | 3000/3000 |
| symmetric_difference    | 3000    | 3000/3000 |
| difference (4 types)    | 4000    | 4000/4000 (fully native Rust) |
| complement (G + D)      | 8000    | 8000/8000 |
| full_join               | 3000    | 3000/3000 |
| disjoint_union          | 3000    | 3000/3000 |
| mycielskian             | 2000    | 2000/2000 |

RESULT: the standalone simple-Graph `intersection` was the LAST instance of the bug
class; everything else builds edges in nx's exact set-& / set-comprehension order. The
buggy ``edge_witness`` one-sided-comprehension pattern was confirmed NOT copy-pasted
anywhere else (only the now-fixed site). intersection_all already used the correct
in-place ``&=`` construction.

## Status
Operator/constructor edge-order fidelity = byte-exact across the surface. No code change
this turn (audit found everything clean post-fix). Generators are native (the remaining
delegated ones — geometric_soft_configuration_graph 145 lines, random_internet_as_graph
AS_graph_generator helper class — are too complex to replicate this turn). The clean
code-only perf veins (generators, redundant-conversion, operators) are mined; remaining
high-value work needs DISK-RECOVERY for the ~27-win deferred-bench batch + substrate Rust.
