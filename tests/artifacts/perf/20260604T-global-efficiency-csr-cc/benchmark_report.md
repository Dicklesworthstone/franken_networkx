# global_efficiency — integer-CSR BFS, String-keyed tax removed (br-r37-c1-geffcsr)

## Problem
`fnx_algorithms::global_efficiency` ran a per-source BFS with `HashMap<&str, usize>` for
distances AND `nbrs.sort_unstable()` (String comparison sort) at every node, then summed
`1/d` over an arbitrary HashMap iteration order. Despite being a "native" kernel this
String-keyed tax made `global_efficiency` ~1.9x SLOWER than networkx (n=150: fnx 13.56ms vs
nx 7.19ms). Same class as the distance_measures / average_shortest_path_length String-BFS tax.

## Lever (ONE)
Replace the per-source `HashMap<&str>` BFS with the integer-CSR BFS pattern already proven on
`average_shortest_path_length` (br-r37-c1-ga0ow): a reused `dist: Vec<usize>` + `seen_stamp:
Vec<u32>` over `graph.neighbors_indices(u)` (index adjacency). The `nbrs.sort_unstable()` is
dropped — BFS distances are independent of neighbour visit order. `1/d` is accumulated at
discovery for each reached target; disconnected graphs contribute only reachable pairs, exactly
like nx's `all_pairs_shortest_path_length`.

## Behavior parity (isomorphism proof)
- Because the index adjacency preserves node-insertion order, the BFS discovery order (and thus
  the `1/d` summation order) matches networkx's `all_pairs_shortest_path_length` order — so the
  result is now **BIT-EXACT** with networkx (the old HashMap-order kernel was only tolerance,
  ~3.3e-16).
- Python sweep: 120 random graphs (n 2..50, p 0.03..0.5, ~30% string-relabelled, includes
  disconnected) — **120/120 within 1e-12, maxdiff = 0.0e+00**. Directed input still raises
  NetworkXNotImplemented; n<2 returns int 0.
- Rust: 11 unit tests pass incl. a new `global_efficiency_matches_networkx_reference` with 6
  nx-captured fixtures (one disconnected) asserted to 1e-12; `pytest -k efficiency` → 79 passed.
- Golden sha256 over nx reference values: `3c1e94a4f736b0fe85a51ce4db56c909261301c8d138c3709fa924be7fe4314e`.

## Benchmark (warm min-of-7, ms)
| n (gnp)   | networkx | fnx before | fnx after | after vs nx |
|-----------|----------|-----------|-----------|-------------|
| 150       | 7.14     | 13.56     | 0.45      | **15.69x**  |
| 300       | 29.26    | —         | 2.23      | **13.11x**  |
| 500       | 86.37    | —         | 7.15      | **12.08x**  |

Before: ~1.9x SLOWER than nx. After: 12-16x FASTER (and bit-exact).

## Score
Impact: very high (1.9x-slower -> 12-16x-faster swing; ~30x self-speedup). Confidence: high
(bit-exact, 120-case + 6 Rust fixtures, 79 tests). Effort: low (one kernel, the proven CSR
pattern). → Score >> 2.0.
