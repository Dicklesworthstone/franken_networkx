# Soundarajan-Hopcroft community link prediction: lazy memoization (br-r37-c1-shlazy)

cn_soundarajan_hopcroft / ra_index_soundarajan_hopcroft computed on the fnx graph
but snapshotted the ENTIRE adjacency (`{n: set(G.neighbors(n)) for n in G}`, plus
degrees) on every call -- the whole-graph O(V+E) cost paid even for a handful of
ebunch pairs. Scoring 10 candidate pairs over n=2000 cost ~12 ms vs networkx's
~0.03 ms (~340-500x SLOWER). The default all-non-edges path also re-did a per-node
community attr lookup (PyO3) for every common neighbour of every pair.

Lever (same class as br-r37-c1-lpconv): lazily memoize neighbour sets / ordered
neighbour lists / degrees / community values, so a small ebunch only touches its
endpoints and the default path looks up each node's community once. ra also now
iterates common neighbours in G.neighbors(u) order and sums with the builtin sum
(networkx's exact common_neighbors order + compensated sum), making it BYTE-exact
(the old set-order naive fold drifted by ULPs on ~28% of cases).

Proof: EXACT tuple-list equality (f == n) vs networkx 200/200 (cn) and 200/200 (ra,
up from 108/150) across default + explicit ebunch, int / string / self-loop graphs;
golden sha256 over both functions on an 80-graph corpus (0 mismatches); 17 existing
Soundarajan-Hopcroft tests pass.

| case | metric | nx | fnx before | fnx after |
|---|---|---|---|---|
| small ebunch n=2000 | cn | 0.034ms | ~12ms | 0.078ms |
| small ebunch n=2000 | ra | 0.027ms | ~12ms | 0.062ms |
| default n=500 | cn | 234.9ms | ~ (snapshot) | 106.0ms (2.22x) |
| default n=500 | ra | 121.9ms | ~ (naive) | 70.1ms (1.74x) |

before: small ebunch ~340-500x SLOWER; default ra 0.65-0.79x (and ULP-divergent).
after:  small ebunch 12ms -> 0.06-0.08ms; default cn 2.0-2.2x / ra 1.6-1.7x FASTER;
        ra now bit-exact vs networkx.
