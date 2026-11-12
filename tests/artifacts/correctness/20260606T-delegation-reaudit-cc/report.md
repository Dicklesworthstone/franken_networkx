# Post-w7nn3 delegation re-audit (rounds 1+2)

## Why
Every delegation "parity-verified" BEFORE e65193c59 was validated
against a conversion that scrambled directed pred rows. Re-verified 42
pred-order-sensitive / tie-break-sensitive fns on tie-rich directed +
weighted-undirected graphs, exact compare (order + objects), with a
SELF-DETERMINISM GATE (call nx twice; skip upstream-nondeterministic
fns instead of false-flagging).

## Results
- 39/42 MATCH — w7nn3 repaired the delegated family wholesale
  (all_shortest_paths, simple_cycles, dominance, edge_bfs/dfs reverse,
  johnson, floyd_warshall, voronoi, condensation, transitive_*, ...).
- hits: NOT an fnx bug — nx.hits itself is call-to-call
  NONDETERMINISTIC on degenerate-gap graphs (scipy 1.17 svds v0=None
  draws a random start; two nx calls differ by 0.8 abs). fnx wrapper
  already mirrors nx's scipy path verbatim. METHODOLOGY: always gate
  exact-compare probes on nx self-determinism.
- topological_generations: REAL BUG, FIXED THIS COMMIT — kernel
  lexicographically sorted each generation (string order: "10" < "2")
  vs nx's node-iteration order (gen 0) / zero-reach order (later), and
  node-map objects vs the zeroing parent's succ-row object. Kernel now
  emits (node, zeroing_parent); golden sha b1e37650, 38-case battery
  incl. multigraph parallel-edge decrement + cycle error.
- stoer_wagner: REAL BUG, FILED br-r37-c1-35oum — native kernel
  returns a different (valid) min-cut partition; needs nx's exact
  maximum-adjacency-search heap tie-breaks.
