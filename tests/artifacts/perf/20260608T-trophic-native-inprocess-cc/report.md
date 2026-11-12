# trophic_levels / trophic_differences / trophic_incoherence_parameter: native in-process (br-r37-c1-trophnative)

## Problem
All three trophic functions delegated to networkx (full fnx->nx conversion + nx
numpy compute) on EVERY call — pure conversion overhead nx never pays.

## Lever (ONE)
Compute in-process via fnx's NATIVE adjacency_matrix + numpy, replicating nx's
exact Levine method `(I - p)^-1 . 1`. The native adjacency_matrix is byte-identical
to nx's, and the remaining numpy is the same, so values match exactly. Shared
strict helper `_trophic_levels_compute` raises nx's exact errors for
no-basal/unreachable/LinAlgError; public trophic_levels keeps the intentional
empty-graph -> {} fnx convention. differences/incoherence build on it, iterating
the edge VIEW `G.edges` (not `edges()`) so MultiDiGraph raises ValueError
identically to nx's own multigraph-unsupported behavior.

## Proof (correctness — no timing; host load avg ~22 this window)
- 60 graphs (DiGraph/MultiDiGraph x weighted/unweighted x self-loops x
  cannibalism T/F): levels 0, diffs 0, incoherence 0 mismatches (value + key
  order + error type/message).
- Error contracts: no-basal / unreachable / undirected / multigraph-ValueError
  all match nx exactly.
- Golden: levels+diffs+incoherence fnx == nx.
- `pytest -k trophic`: 22 passed.

Structural win: eliminates the per-call fnx->nx conversion for all three; benefit
is load-independent (host saturated at load ~22 this window precludes a clean
vs-nx ratio, but the conversion removal is provable by construction).
