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

## Follow-up: the u-major-hoist class generalized (same session arc)
MECHANISM CORRECTED: edges_ordered() is NOT sorted — it is a u-major
adjacency walk that HOISTS reverse-orientation cells to the u side
(same family as the copy()-walk and w7nn3 conversion classes). Swept
the remaining rebuild sites:
- rust_digraph_to_py_standalone: succ rows survived the rebuild but
  PRED rows scrambled — now wholesale clone_with_fresh_policy.
- ALL SIX MultiGraph/MultiDiGraph -> simple projections (used by every
  algorithm on Multi classes via GraphRef): rebuilt rows hoisted —
  OBSERVABLE bug: BFS/DFS tie-breaks on MultiGraphs diverged from nx
  when traversing from a node holding a hoisted back-edge (probe
  needed the right shape: from-the-hoisted-node; the first probe from
  elsewhere passed because the hoisted neighbor was already visited).
  Projections now apply_row_orders from the source.
Battery sha db7a82ae (repro + 25-trial random multigraph traversal
corpus); full pytest 21790 passed.

## Workaround re-enablement audit (post converter fix)
Probed every "route Python always / order drift" workaround against
the now-faithful converters:
- wheel_graph (o97vk): kernel was NEVER wrong — converter hoisting was
  the whole bug. Native fast path RE-ENABLED (n=0..14 + iterable +
  create_using validated).
- transitive_reduction (utmy6): 4-node probe matched but a 40-DAG
  corpus shows the KERNEL's own edge emission order diverges (succ-row
  order within result rows) — delegation STAYS. Lesson: one-shape
  probes lie; corpus before re-enabling.
- cycle/dodecahedral/frucht (o97vk/iw2hz): kernels genuinely diverge
  (petersen-class wrong emission) — workarounds stay; kernel emission
  fixes are future candidates.

## cycle_graph kernel fix + re-enablement
The cycle kernel emitted the closing edge SECOND as (0, n-1); nx's
cyclic pairwise emits it LAST as (n-1, 0) — row n-1 was [0, n-2] vs
nx [n-2, 0]. Kernel loop is now the modular (i, i+1) walk; the
kernel's own unit test was rewritten to assert ADJACENCY ROWS (the old
expectation codified the u-major snapshot order, masking the bug).
Native route re-enabled (n=0..12, iterable, create_using, and the
cycle-composing builders tadpole/circular_ladder/lollipop validated).
dodecahedral/frucht remain on Python paths (LCF/named constructions —
separate kernels, future fixes).

## dodecahedral + frucht kernels fixed; ALL generator workarounds retired
Both kernels used sorted-pair edge lists (same edge SET, divergent
rows — dodecahedral had 11 divergent rows). Rewritten to nx's exact
sequences: dodecahedral = LCF 20-cycle + 40 shift edges in LCF order;
frucht = cycle(7) modular walk + nx's 11-edge list in its order.
Native routes re-enabled (default case; create_using keeps Python).
The generators arc is COMPLETE: 29/29 matrix clean, zero remaining
'route Python always' workarounds for row drift (wheel, cycle,
tadpole, dodecahedral, frucht all native; transitive_reduction stays
delegated on corpus evidence).
