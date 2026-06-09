# s_metric: integer-CSR native kernel — 11.5x FASTER than nx (br-r37-c1-yxmdc)

## Problem
nx.s_metric is pure Python (sum deg(u)*deg(v) over edges). fnx's Python loop was
3.4x SLOWER (slow per-edge G.edges() dispatch). The native _fnx.s_metric kernel
existed but (a) was UNUSED, (b) was itself SLOWER than nx (2.57ms vs 1.87ms) and
(c) mishandled self-loops.

## Root cause + lever (ONE)
The kernel did a String-keyed `neighbor_count(nbr)` HashMap lookup PER EDGE
(2|E| hashes — the String-adjacency tax) and used `neighbor_count` (self-loop
once) + a blanket `/2`. Rewrote to integer-CSR: precompute degrees by INDEX once
(`degree_by_index` = nx's self-loop-aware degree, counts self-loop twice), then
sum deg[u]*deg[v] over each undirected edge EXACTLY ONCE via a `v >= u` filter
(self-loop u==u counted once). u128 accumulation is exact + order-invariant.
This fixes self-loops (gate dropped to undirected/simple) AND kills the tax.

## Proof
- Parity 0/240 (Graph/DiGraph/MultiGraph/MultiDiGraph x self-loop[0,1,7,25] x 15
  seeds); empty graphs match; golden fnx==nx. pytest -k s_metric 64 passed.
- Speed n=1500 (with 50 self-loops): native kernel 2.57ms -> 0.171ms (15x self);
  vs nx 1.96ms -> ratio 0.09x = 11.5x FASTER than nx (was 3.4x slower).

The 0.09x ratio is unambiguous under host load (load ~20 this window); the win is
structural (integer-CSR eliminates 2|E| String hashes, the canonical fnx tax).
