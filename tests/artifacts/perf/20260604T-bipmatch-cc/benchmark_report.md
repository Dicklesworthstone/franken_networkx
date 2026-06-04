# bipartite matching: one-shot nx view instead of nx-on-fnx (br-r37-c1-bipmatch)

fnx.bipartite re-exported networkx's matching functions verbatim
(`from networkx.algorithms.bipartite import *`), so
`fnx.bipartite.hopcroft_karp_matching(F)` ran networkx's algorithm directly over
the fnx graph -- every adjacency access pays the String-keyed PyO3 substrate cost,
and Hopcroft-Karp / Eppstein sweep the adjacency many times -> 3-6x SLOWER than
networkx.

Lever: override hopcroft_karp_matching / maximum_matching / eppstein_matching to
convert ONCE to a plain nx graph (lightweight: nodes + edges, no attributes; node
order + B.edges() order preserved so adj[u] matches a directly-built nx graph) and
let networkx's C-speed adjacency carry the repeated sweeps. nx-typed inputs pass
through unchanged.

Proof: parity vs networkx 0 mismatches over 120 bipartite graphs x 3 functions x
{top_nodes, None} + nx-typed-input passthrough (1800/1800); golden sha256; 426
existing bipartite tests pass. Matching is byte-identical because the converted
graph's adjacency order matches the original.

| n (per side) | fn | OLD nx-on-fnx | NEW override | speedup |
|---|---|---|---|---|
| 80 | hopcroft_karp | 2.73ms | 1.10ms | 2.47x |
| 160 | hopcroft_karp | 10.56ms | 4.16ms | 2.54x |
| 160 | eppstein | 12.32ms | 5.92ms | 2.08x |

before: 3-6x SLOWER than nx (nx algorithm over fnx substrate, many adj sweeps).
after:  2.0-2.5x faster than before. Residual vs nx-on-nx is the one-shot
        conversion cost (reading fnx edges); a native Hopcroft-Karp kernel would
        beat nx outright.
