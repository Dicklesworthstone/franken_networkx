# br-r37-c1-z2eaa — native kneser_graph kernel

## Gap (warm min-of-5)
kneser(9,3) 16.58x / kneser(11,4) 17.19x slower than nx. Same
abandoned-for-label-shape class as grid_2d (ab83e6b33): old br-kneser
path emitted "0,1" strings.

## Lever (one): native kernel with proven set-order gate
- fnx_classes::Graph::kneser replicates nx verbatim: lex k-subsets,
  edge stream `for s in subsets: for t in combos(universe - set(s), k)`
  with node FIRST-TOUCH creation (u then v) and structural-no-op dup
  adds skipped via a seen-pair set; t located by lexicographic
  combination ranking (binomial table); 2k>n pre-adds isolated nodes.
- The nx complement is a CPython SET — its iteration is ascending iff
  every value < the set's final table capacity (exact-slot property,
  insertion-history independent). The wrapper SIMULATES CPython's
  growth rule and gates the kernel on (n-1) < cap(n) and < cap(n-k);
  unsafe shapes fall back to the pure-Python build (which matches nx by
  construction). Analysis: failing the gate with 2k<=n needs n>=2049,
  k>=821 — C(n,k) astronomically unbuildable, so every practical call
  takes the kernel; the fallback is correctness-in-principle insurance.
- Binding emits PyTuple subset display keys (y7m24 canonicals).

## After
kneser(9,3) 0.50x / (11,4) 0.47x / (14,2) 0.52x — 2x FASTER than nx.
Score: ~34x self-speedup crossing parity => >>2.0.

## Proof
- 85-case matrix: exhaustive n in 1..=12 x k in 1..=n (isolated-node
  2k>n shapes, k=1, k=n, petersen), validation errors, big shapes;
  canon = nodes+edges+adjacency rows reprs; 0 failures.
  GOLDEN_SHA256 019ed6ae7f175c85f1fafda8c8edf5eee02ec6f89936c7507a4ede6d9ac3d28a
- tuple-type pins, membership/has_edge, is_isomorphic(petersen),
  mutation-after-build, pickle round-trip, copy.
- 5 new committed test classes (292 generator-suite tests green);
  full pytest 21572 passed, 0 failed.
