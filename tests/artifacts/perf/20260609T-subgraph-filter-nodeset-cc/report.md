# perf(subgraph): bulk node-set membership in nbunch filter

br-r37-c1-50w8n

## Problem
subgraph(G, nbunch) already returns a VIEW (subgraph_view), but cProfile showed
construction was 5-6x slower than nx: `_subgraph_filter_from_nbunch` did a
per-node `node in G` check, and fnx's `Graph.__contains__` is a Python override
(_private_override + vars(), ~0.8us each) vs nx's C-dict lookup. For a V/2-node
nbunch that's V/2 slow membership tests.

## Lever (one)
Build `set(G)` ONCE and test membership at C speed — gated to only build the
O(V) set when nbunch is large enough to amortize (>= ~V/4 nodes); a tiny nbunch
on a large graph keeps the per-node path (no whole-graph over-build). Error
contract preserved (unhashable node / non-iterable nbunch -> NetworkXError, via
list(nbunch) + per-node hash()).

Touched: python/franken_networkx/__init__.py (_subgraph_filter_from_nbunch).

## Proof (nx-exact)
595 cases (random gnp n=0..45 x nbunch forms: full/half/single/with-absent/
empty) 0 mismatches vs nx (nodes + edges). Error parity: unhashable-elem /
float / opaque-object nbunch all raise NetworkXError like nx. pytest -k
"(subgraph or induced) and not mutation": 321 passed; regression-lock subgraph
tests: 25 passed.
SUBGRAPH_SHA fb47dd2f33c0fb5f68ad0205128f27433af30e0b0ce6e749760e69182f3f5082

## Timing (warm min-of-8)
| case                    | nx     | before | after  | ratio before -> after |
|-------------------------|-------:|-------:|-------:|----------------------:|
| BA n=400, nbunch=V/2    | 12.5us | 62.3us | 25.9us | 4.9x -> 2.1x (2.4x faster) |
| BA n=1600, nbunch=V/2   | 40.8us | 255us  | 94.7us | 6.4x -> 2.3x (2.7x faster) |
| BA n=4000, nbunch=3     |  6.1us |  5.6us |  6.1us | no regression (gate skips set build) |

Residual ~2.1-2.3x is the set(G) iterator cost (substrate node iteration, owned
by br-r37-c1-04z53.60) + view construction — this lever closes the per-node
__contains__ portion.

## Score
Impact: moderate-high (common op, 2.4-2.7x self-speedup, 5-6x->2.1-2.3x).
Confidence: high (0/595 vs nx + error parity, 321 tests). Effort: low. Score >= 2.0.

## Note
2 unrelated failures (test_graph_iteration_detects_node_mutation*) are from a
peer's in-flight substrate iteration WIP (same-size-mutation RuntimeError parity,
br-r37-c1-04z53.60) present in the working tree / installed extension — NOT this
change (pure-Python subgraph filter; all subgraph tests pass).
