# transitivity / clustering / average_clustering: mark-array each-triangle-once kernel (br-r37-c1-yxmdc)

## Problem
All three route through fnx_algorithms::clustering_coefficient, whose triangle
counting used per-node `directed_triangle_hits`: for each node it scanned EVERY
neighbor's FULL adjacency row and counted each triangle twice (then /2). ~4x the
necessary inner work -> transitivity 2.09x, clustering 2.28x, average_clustering
2.20x SLOWER than nx (which is pure Python).

## Lever (ONE)
Count each triangle EXACTLY ONCE via a reusable mark array + a u<v<w ordering,
incrementing all three vertices' per-node counts. Precompute non-self degrees for
total_triples. Per-node coefficient, average_clustering, and transitivity are all
computed from the same totals as before -> bit-identical outputs.

## Proof
- Parity 0/360: transitivity (scalar) + clustering (per-node dict) +
  average_clustering, over 40 seeds x self-loop[0,1,10], to 1e-12; golden
  transitivity float-EXACT == nx. pytest -k clustering/transitivity/triangle:
  762 passed.
- Speed n=500 deg8:
  - transitivity      12.89ms -> 0.33ms : 2.09x slower -> 17.5x FASTER than nx
  - clustering        13.24ms -> 0.45ms : 2.28x slower -> 12.8x FASTER
  - average_clustering        -> 0.46ms : 2.20x slower -> 12.6x FASTER

Structural win (u<v<w + each-triangle-once eliminates the directed double-count
and full-row rescans); the 0.06-0.08x ratios are unambiguous under host load.
