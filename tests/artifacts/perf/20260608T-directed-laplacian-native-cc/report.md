# directed_laplacian_matrix / directed_combinatorial_laplacian_matrix: native in-process (br-r37-c1-dirlapnative)

## Problem
Both directed Laplacian matrices delegated to nx every call (full fnx->nx
conversion + nx compute). The prior bespoke native version was wrong (missing
walk_type, always pagerank), and the delegation comment claimed reproducing nx's
walk_type table "without drift is brittle".

## Lever (ONE)
Port nx's exact Chung directed Laplacian in-process: shared
`_directed_transition_matrix` (random/lazy/pagerank, default selected via native
is_strongly_connected/is_aperiodic) built from the native to_scipy_sparse_array,
then the SINGLE Perron-vector eigensolve `scipy.sparse.linalg.eigs(P.T, k=1)` +
`v/v.sum()` normalization (sign-/scale-unique => deterministic). Same scipy on the
same P => byte-matches nx. Drops the per-call conversion. Callable weight delegates.

## Proof (correctness — no timing; host load avg ~35 this window)
- directed_laplacian_matrix: 0/480 mismatches; directed_combinatorial: 0/480
  (walk_type=None / pagerank / strong+random/lazy x weighted x 40 seeds).
- The ONLY divergent combo — forced random/lazy on a NON-strongly-connected graph
  — is mathematically undefined (dangling-node divide-by-zero -> inf/nan through
  ARPACK) and verified NON-deterministic in nx ITSELF (nx-vs-nx not self-consistent),
  so it is out of the defined domain.
- Error contracts: undirected/multigraph -> NetworkXNotImplemented (decorator
  order), bad alpha / bad walk_type -> NetworkXError. All match nx.
- Golden fnx == nx (rounded matrices).
- `pytest -k laplacian/directed_lap/combinatorial`: 156 passed.

Structural delegation-elimination (load-independent).
