# constraint / effective_size (nodes=None): native matrix path, drop fnx->nx delegation (br-r37-c1-qurfc)

## Problem (perf-BLOCKED bead)
constraint/effective_size delegated to nx (~4x, full fnx->nx conversion) for
weight!=None / directed / self-loop graphs. The bead presumed the value was
set-iteration-order-dependent (ULP wall).

## Key finding
nx's constraint/effective_size with nodes=None use a DETERMINISTIC MATRIX path
(P + P.T row-normalized + sparse matmul), NOT the set-order summation. The
set-order ULP wall ONLY affects the nodes!=None set path. The matrix path is
byte-reproducible because fnx's native adjacency_matrix is byte-identical sparse
to nx's (csr_array, same data/dtype).

## Lever (ONE)
Route the nodes=None delegated cases through nx's verbatim matrix path in-process
over the native adjacency_matrix. nodes!=None stays delegated (set-order path).

## Proof (correctness — no timing; host load avg ~15 this window)
- MY matrix-path domain (weighted/directed/self-loop, nodes=None): constraint
  0/350, effective_size 0/350 EXACT (value incl nan + key order).
- nodes!=None still delegates -> matches; golden weighted fnx==nx (directed x
  self-loop); structuralholes test suite 506 passed (1 xfail).

## Note (separate pre-existing issue, NOT touched here)
The unweighted-undirected constraint_rust path has its OWN ~1-ULP divergence vs
nx (43/50 on random n=13 graphs) — filed as a separate bead; the matrix path is
the byte-exact fix there too if it doesn't regress that path's perf.
