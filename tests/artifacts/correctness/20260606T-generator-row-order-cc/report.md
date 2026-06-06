# Generator row-order parity (matrix: 29 generators)

## Found (probe archived here)
2 visible divergences (tadpole, sudoku) + 1 MASKED (petersen).
Root cause: rust_graph_to_py_standalone REBUILT kernel graphs from
edges_ordered() — canonical-key SORTED iteration — scrambling
adjacency rows for any kernel with non-sorted insertion order, and
conversely MASKING kernels whose own emission order was wrong but
whose rows happen to be sorted in nx (petersen via
generalized_petersen(5,2)). The old wheel_graph Python-path
workaround (br-r37-c1-o97vk) was this same bug class.

## Fixed
- rust_graph_to_py_standalone: wholesale inner clone_with_fresh_policy
  (no rebuild; rows preserved exactly; lazy mirrors; fresh ledger).
- sudoku kernel: nx's three-pass construction (also O(n^6) -> O(n^4·n^2)
  vs the all-pairs scan).
- petersen kernel: nx's small-graph adjacency-list walk (the
  generalized-petersen construction is isomorphic but row-divergent).

## Certified clean (29/29)
barbell lollipop circular_ladder ladder wheel star turan
complete_multipartite caveman connected_caveman dorogovtsev
full_rary_tree binomial_tree balanced_tree path(0) null trivial
tadpole complete/cycle(DiGraph) path/star(iterables) hypercube
triangular_lattice hexagonal_lattice sudoku chvatal petersen
mycielski. Full pytest 21776 passed, 0 failed.
