# rich_club_coefficient: O(V+E) native sweep — fix correctness bug + 2.87x FASTER than nx (br-r37-c1-richclub)

## Problems
1. PERF: the Python wrapper used a pure-Python port of nx's _compute_rc whose
   bottleneck was `G.edges()` iteration + sort -> 2.69x SLOWER than nx.
2. CORRECTNESS: the native kernel (UNUSED, bypassed by the wrapper) was O(D*|E|)
   AND keyed on the distinct degree VALUES — it returned {3:0.0} for K4 where nx
   returns {0:1,1:1,2:1}. Its Rust unit tests locked in the bug.

## Lever
Rewrote the native kernel to nx's EXACT O(|V|+|E|) sweep (integer-CSR): degree
histogram -> N_d via prefix sums; sort the per-edge smaller-endpoint degree once
-> sweep popping edges as the threshold rises; phi(d)=2*E_d/(N_d*(N_d-1)) for each
degree d with N_d>1, emitted in ascending-d order. Route the wrapper to it.

## Proof
- Parity 0/40 dense + 0/3 non-consecutive-degree (star+isolated / barbell / path,
  keys+values+order); K4 now {0:1,1:1,2:1} == nx (bug fixed); normalized=True OK;
  Rust unit tests updated to nx-correct values + 37 pytest passed.
- Speed n=400 deg8 (interleaved min-of-15): fnx 0.604ms vs nx 1.743ms = 2.69x
  slower -> 0.35x = 2.87x FASTER than nx.
