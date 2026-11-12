# perf: powerlaw_cluster_graph O(n^2) -> O(n) + integer-adjacency clustering (br-r37-c1-n5c3e)

## Root cause (the real lever)
`random_subset_python_cpyset_order` (the sole helper powerlaw calls once per
source) computed `unique_cap` by inserting the ENTIRE `seq` into a BTreeSet on
every call. In powerlaw_cluster `seq` is the ever-growing `repeated_nodes`
(length O(n*m)), so the per-source rescan made the generator O(n^2 * m * log).
`unique_cap` is only used to clamp the draw count for the degenerate
"fewer-than-count distinct values" case — which never occurs in powerlaw
(`repeated_nodes` is seeded with 0..m and only grows). Pass `unique_cap` in,
maintained incrementally via a `repeated_unique: HashSet<usize>` kept in lockstep
with `repeated_nodes`. The RNG draw sequence is unchanged -> byte-identical.

## Secondary lever
The clustering candidate scan used `graph.neighbors(target)` (allocates a
Vec<&str> + `parse::<usize>` per neighbour) and `graph.has_edge(source, nbr)`
(String-keyed) every step. Node labels equal node indices (nodes added
"0".."n-1"), so `neighbors_indices(target)` yields the candidates as usize in
the SAME adjacency insertion order (preserving the order that feeds
`rng.choice_index`), and a tracked `source_neighbors: HashSet<usize>` reproduces
`has_edge(source, ...)` (source is a fresh node) without the String lookup.

## Correctness (byte-exact)
750-case differential vs networkx (n in {20,50,100,200,400} x m in {1,2,3,4,6}
x p in {0,.1,.3,.5,.9,1.0} x 5 seeds; p up to 1.0 = max clustering), 0 mismatches
on EXACT edge + node order. golden sha 8ad06e40 (UNCHANGED from the buggy
version -> proves the optimization is behaviour-preserving). fnx-generators
cargo tests: 194 passed.

## Perf (warm min-of-8)
| case               | before  | after   | self-speedup | vs nx (after) |
|--------------------|---------|---------|--------------|---------------|
| n=400  m=4 p=0.1   | 11.48ms | 2.87ms  | 4.0x         | 1.61x         |
| n=1000 m=5 p=0.3   | 122.6ms | 10.37ms | 11.8x        | 1.25x         |
| n=2000 m=4 p=0.5   | 456.3ms | 19.81ms | 23.0x        | 1.27x         |
| n=500  m=3 p=0.9   | 13.8ms  | 3.13ms  | 4.4x         | 0.94x (beats) |

powerlaw_cluster went from 6.8-29.5x slower than nx to 0.94-1.61x (parity).
