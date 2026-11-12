# triadic_census: O(n^3) all-triples -> O(m*d) Batagelj-Mrvar

Bead: `br-triadbm`.

## Catastrophe

The Rust `triadic_census` kernel (`fnx-algorithms/src/lib.rs`) enumerated EVERY
node triple `for i: for j>i: for k>j` and classified the 6 directed edges among
each -- **O(n^3)**. A vs-nx domain sweep (warm min-of-3) measured fnx **6.43x
SLOWER** than networkx on a sparse directed graph (n=300, gnp p=0.02: fnx 0.393s
vs nx 0.061s). networkx uses the subquadratic Batagelj-Mrvar algorithm.

## Lever (one)

Replace the triple loop with Batagelj-Mrvar (the same algorithm networkx uses,
but in Rust). For each ordered dyad `(v, u)` with `u` after `v`, only the shared
neighborhood `neighbors = (nbrs[v] | nbrs[u]) \ {u, v}` is visited; each connected
triad is counted once via the ordering guard
`u < w || (v < w < u && v not in nbrs[w])`, with the 6-bit `_tricode` lookup
(`TRICODES[code] -> triad type`). Triads whose third node is unconnected to the
dyad are added in O(1) (`N - len(neighbors) - 2`), and `003` is back-solved from
the total. Complexity drops to **O(m * d_max)**.

Census counts are independent of node ordering, so the Rust index order is a
valid total order and yields the IDENTICAL 16 cell counts.

## Isomorphism / golden proof

`parity_golden_and_small_triads.py`: 120 random directed graphs (n up to 45,
with injected mutual edges), the full 16-cell census hashed:

    parity: 120/120 graphs match
    golden_sha256_fnx = 145b337b586ff928dffe9eb0408cea204d830ceec73f2cca9649e95a418f5954
    golden_sha256_nx  = 145b337b586ff928dffe9eb0408cea204d830ceec73f2cca9649e95a418f5954
    ISOMORPHISM: PASS

All 16 triad types verified individually; sum == n(n-1)(n-2)/6; n<3 all-zero;
undirected raises; nodelist form (delegates to nx) unchanged. Rust unit tests
`test_triadic_census_{empty,cycle}` pass.

## Benchmark (warm min-of-4, sparse gnp directed)

    n      avgdeg   nx(s)     fnx(s)    speedup
    200     5.7     0.0414    0.0030     13.7x
    400     6.0     0.0970    0.0062     15.7x
    700     7.1     0.2216    0.0162     13.6x
    1200    7.1     0.3924    0.0266     14.7x

fnx swings from 6.43x SLOWER to ~14x FASTER than networkx (a ~90x relative
improvement), and the win grows with n (O(n^3) -> O(m)). Score: Impact (~90x
relative, complexity class) x Confidence (1.0, exact golden) / Effort (~2) >> 2.0.

## Files

- `crates/fnx-algorithms/src/lib.rs`: `triadic_census` Batagelj-Mrvar rewrite.
- `tests/python/test_triadic_census_batagelj_mrvar_parity.py`.
