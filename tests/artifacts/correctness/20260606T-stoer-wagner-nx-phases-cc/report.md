# br-r37-c1-35oum — stoer_wagner nx-exact partition

## Bug (from the post-w7nn3 re-audit)
Native kernel was a textbook linear-scan maximum-adjacency search:
same min-cut VALUE but a different (valid) partition than nx on
tie-rich graphs (repro seed 7: fnx (['11'], rest) vs nx (['4'], rest)).

## Fix — split by what each side can replicate
- Rust kernel stoer_wagner_nx mirrors nx's phases LINE BY LINE:
  working copy from the u-major edge stream, per-phase lazy-deletion
  min-heap with INSERTION-COUNTER tie-breaks (networkx BinaryHeap
  semantics; -0.0 == 0.0 so the counter decides), arbitrary_element =
  first node in copy order, contraction merges in G[v] row order,
  order-preserving node removal. Returns (cut_value, contractions,
  best_phase, copy_nodes-with-first-touch-parents).
- Python wrapper runs nx's partition-recovery tail VERBATIM with real
  CPython sets (list order = set-iteration order — unreplicable in
  Rust, exact by construction in-process).
- Display objects: copy v-positions carry the (u, v) row object
  (discovery-object convention).

## Proof
Golden sha 1d4fa715: re-audit repro, nx docstring example, 50-trial
tie-rich corpus (unweighted / weighted / zero-weight / mixed-default),
error contracts (negative weight, disconnected, < 2 nodes), integral
cut-value TYPE (int vs float). 0 failures. Full pytest 21669 passed.
Re-audit round 2 now FULLY clean (42/42 after hits methodology note).
