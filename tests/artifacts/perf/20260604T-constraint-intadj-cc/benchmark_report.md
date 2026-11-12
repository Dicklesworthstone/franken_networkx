# constraint: integer-adjacency mark-array kernel (br-constraint-intadj)

Burt's `constraint` used the native `constraint_rust` kernel but was ~3.1x SLOWER
than networkx: it rebuilt `graph.neighbors(v)` (a String-keyed Vec + HashSet
allocation) for every (u,v) pair, plus another `graph.neighbors(w)` per common
neighbor -- ~2m repeated neighbor materializations. networkx wins the Python race
via an `lru_cache` on normalized_mutual_weight.

Lever: precompute integer adjacency once, then run the same double sum with a
reusable mark-array (bool scratch marking N(u)) and a per-node accumulator,
iterating the middle node w over N(u) and fanning out over N(w). No hashing, no
per-pair allocation; O(sum deg^2) work with O(1) array probes. The accumulation
order and operands are byte-identical to the old kernel (term = p*(1/deg_w),
summed per v in w-order), so float outputs are unchanged.

Proof: golden sha256 over fnx.constraint on an 80-graph corpus is IDENTICAL before
and after (42eace5c...); 305/305 parity vs networkx (300 random gnp + complete/
star/cycle/path/empty/subset fixtures); 79 existing structural-holes tests pass.

Warm min-of-11 (gnp):

| n | m | nx (ms) | fnx (ms) | speedup |
|---|---|---|---|---|
| 800 | 3163 | 4.380 | 3.538 | 1.24x |
| 1000 | 9974 | 24.478 | 8.400 | 2.91x |
| 1500 | 9008 | 17.393 | 8.861 | 1.96x |
| 2000 | 10025 | 17.859 | 10.801 | 1.65x |
| 500 | 3789 | 8.125 | 3.369 | 2.41x |

before: 3.11x SLOWER (n=800).  after: 1.24x-2.91x FASTER.
