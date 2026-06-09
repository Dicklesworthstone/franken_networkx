# onion_layers: O(V+E) bucket-queue peel — 4.5-32x FASTER than nx (br-r37-c1-onionbucket)

## Problem
onion_layers was 2-3x SLOWER than nx. Both the kernel AND nx re-`sorted(degrees,
key=degrees.get)` over ALL survivors every layer -> O(|V|^2 log) on many-layer
graphs (a 2000-node path = ~45ms fnx / ~16ms nx). The kernel also built adjacency
with a String node->index map + per-edge String lookups.

## Lever (ONE, complexity class)
Integer-CSR adjacency + a LAZY DEGREE-BUCKET queue: O(1) min-degree (advance a
pointer, pop stale entries), O(1) decrement moves (push to the lower bucket).
Per layer, only the nodes actually peeled are TOUCHED and sorted by
(degree asc, insertion-index) — reproducing nx's exact within-layer order — so
the total is O(|V| log d_layer + |E|) instead of O(|V|^2 log).

## Proof
- Parity 0/240 value + key ORDER (60 seeds x isolated[0,5] x int/string keys);
  karate club order matches; 68 pytest passed.
- Speed (interleaved min-of-11), all parity-True:
  - path2000   16.51ms -> 0.51ms = 32.3x FASTER
  - grid40x40   2.49ms -> 0.39ms =  6.5x FASTER
  - tree2000    2.27ms -> 0.47ms =  4.8x FASTER
  - ba2000m2    2.16ms -> 0.48ms =  4.5x FASTER
  - dense500d8  1.02ms -> 0.15ms =  6.8x FASTER (was 2.04x slower)
