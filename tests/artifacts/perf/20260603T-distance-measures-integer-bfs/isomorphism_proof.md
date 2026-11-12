# distance_measures integer-BFS lever (br-r37-c1-l4ujg)

## Change
`distance_measures` (powers diameter/radius/eccentricity/center/periphery) ran a
BFS from every source using a freshly-allocated per-source
`HashMap<&str, usize>` distance map + `neighbors_iter` (String-keyed adjacency).
For |V| sources that is |V| String-keyed BFS — O(|V|*(|V|+|E|)) with a string
hash on every node touch and every edge scan.

New: integer-indexed BFS over the CSR adjacency (`neighbors_indices`), with a
single reused `dist: Vec<usize>` and a per-source `seen_stamp: Vec<u32>` (stamp =
src_idx+1) giving O(1) reset between sources instead of allocating a map each time.

## Why output is bit-identical
Unweighted BFS distances are independent of neighbor iteration order, so each
node's eccentricity (max distance to any reachable node) is unchanged.
`adj_indices` is maintained in the same insertion order as the string adjacency,
so node-touch/edge-scan/queue-peak witness counts are also identical. Eccentricity
entries are pushed in `nodes_ordered()` order (unchanged); diameter=max,
radius=min, center/periphery = nodes at radius/diameter then sorted — all
order-invariant. No FP, no RNG.

`ecc` is now tracked as the max distance popped (BFS pops in non-decreasing
distance) — equal to the old `dist.values().max()`.

## Verification
dm_golden.py: diameter/radius/eccentricity/center/periphery vs networkx across
BA(800,5),(400,3),(150,4),(60,2). 20 cases, 0 mismatches, digest unchanged:

    DM_GOLDEN 1732156e35a1e36dff16127eca34ddc89d763f2646891daf24b1a73426cef998

1194 distance/eccentricity pytest cases + 7 fnx-algorithms rust tests +
clippy -D warnings pass.

## Benchmark (same-window stash before/after, diameter on BA(1200,5))
    before (String-keyed HashMap BFS): 563.4 ms
    after  (integer CSR BFS):           34.4 ms   -> 16.4x
Now ~20x faster than networkx (703 ms).

Opportunity Score = Impact 5 x Confidence 5 / Effort 2 = 12.5.
