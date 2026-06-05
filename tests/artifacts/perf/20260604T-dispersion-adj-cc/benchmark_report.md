# dispersion: precomputed adjacency sets (br-r37-c1-dispadj)

The dict form of `dispersion` recomputed `set(G.neighbors(x))` from the
String-keyed substrate for every (node, nbr) pair AND every common neighbour
s/t inside `_dispersion_pair` -- O(E * embeddedness^2) neighbour
materializations that left fnx ~3x SLOWER than networkx (which walks its
native dict adjacency directly).

Lever: precompute every adjacency set ONCE (`adj = {n: set(G.neighbors(n)) for
n in G}`) and reuse it in `_dispersion_pair_cached`. The set logic is identical
and `disp` is an order-invariant integer count, so every float result is
byte-for-byte unchanged.

Proof: golden sha256 over fnx.dispersion (full dict form) on an 80-graph corpus
IDENTICAL before and after (d9d18eef...); 504/504 value parity vs networkx
(normalized/alpha/b/c variations, single-node form, karate/lesmis/complete/cycle
fixtures); 8 existing dispersion tests pass.

Interleaved min-of-13:

| n | m | nx (ms) | fnx (ms) | speedup |
|---|---|---|---|---|
| 80 | 324 | 1.178 | 0.971 | 1.21x |
| 120 | 447 | 1.388 | 1.187 | 1.17x |
| 150 | 938 | 4.124 | 3.261 | 1.26x |
| 200 | 1025 | 3.395 | 2.804 | 1.21x |
| 300 | 1867 | 6.763 | 5.565 | 1.22x |

before: 0.31x-0.33x SLOWER (~3x).  after: 1.17x-1.26x FASTER.
Residual is the pure-Python common-neighbour double loop; a native integer-bitset
dispersion kernel is the deeper follow-up (filed).
