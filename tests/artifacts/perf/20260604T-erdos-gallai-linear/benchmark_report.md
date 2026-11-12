# is_graphical (Erdos-Gallai): O(n^2) -> O(n log n)

Lever: is_valid_degree_sequence_erdos_gallai recomputed sum(seq[:k]) and
sum(min(d, k) for d in seq[k:]) for EVERY k -- O(n^2) over the n inequalities.
On a 400-degree sequence that made fnx ~30x slower than nx (a basic
combinatorial predicate). Precompute prefix sums and binary-search the
sorted-descending crossover where the degrees drop below k, so each
Erdos-Gallai inequality is O(log n):
  sum(min(d, k) for d in seq[k:]) = (p - k) * k + sum(seq[p:]),
  p = max(k, #{d : d >= k}).
A complexity-class change, not a loop tweak.

## Benchmark (degree sequence of watts_strogatz(N,.,.))

| N   | fnx BEFORE | fnx AFTER | nx       |
|-----|------------|-----------|----------|
| 400 | 2.817 ms   | 0.106 ms  | 0.105 ms |
| 600 | ~6 ms      | 0.215 ms  | 0.163 ms |

~27x faster; now at parity with nx.

## Isomorphism proof

Boolean result bit-identical to the previous implementation AND networkx over
3068+ sequences x {eg, hh} methods (random length-1..18 sequences, real
graphical sequences from random graphs, and edge cases: empty / single /
odd-sum / over-degree); direct is_valid_degree_sequence_erdos_gallai matches nx
on 500 random sequences; invalid method raises NetworkXException
(test_is_graphical_linear_erdos_gallai_parity, 4 cases). 16 existing
graphical/degree-sequence tests pass.

is_graphical is a building block for degree-sequence generators
(havel_hakimi_graph, configuration validation), so the complexity-class fix
compounds wherever it is called in a loop.
