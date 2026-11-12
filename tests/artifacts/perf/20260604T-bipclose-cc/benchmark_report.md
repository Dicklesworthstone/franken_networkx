# bipartite.closeness_centrality — native single-source BFS (br-r37-c1-kp3o0)

## Problem
`franken_networkx.bipartite` does `from networkx.algorithms.bipartite import *`, so
`bipartite.closeness_centrality` ran networkx's Python implementation directly over the
fnx graph. Its hot loop is one `single_source_shortest_path_length` BFS per node, each
paying the String-keyed PyO3 adjacency tax on every neighbor access — ~1.2x slower than
networkx on a native graph (0.83-0.84x in the bipartite sweep).

## Lever (ONE)
Override `closeness_centrality` in `python/franken_networkx/bipartite.py` with networkx's
exact algorithm, but source each BFS from `fnx.single_source_shortest_path_length` (native
kernel) instead of letting nx's pure-Python BFS walk the fnx adjacency.

## Behavior parity (isomorphism proof)
Every output value derives from integer hop-count sums (`totsp = sum(sp.values())`) and
integer set cardinalities (`len(sp)`, `len(top)`, `len(bottom)`, `len(G)`); the only float
operations are deterministic divisions. Result is therefore byte-identical to networkx —
values AND dict key order (closeness is built by iterating `set(nodes)` then
`set(G) - set(nodes)`, identical to nx).

- Parity sweep: 90 cases (40 random bipartite graphs × seeds, davis_southern_women,
  path/star/complete-bipartite, self-loop+isolated; normalized True/False) — **0 mismatches**,
  key order included.
- Directed and multigraph spot-checks: bit-exact.
- Golden sha256 over all (graph, normalized, node, value) tuples: see golden_sha256.txt
  (`d2af3af3dad2313285200bb0bd37a6c2a57a791c08b910dc141fe62ea7742487`).
- Existing suite: `pytest -k bipartite` → 432 passed.

## Benchmark (min-of-11, ms)
| graph (top+bottom, p) | networkx | fnx (after) | speedup |
|-----------------------|----------|-------------|---------|
| 120+120, p=0.08       | 18.321   | 6.756       | 2.71x   |
| 250+250, p=0.05       | 87.589   | 32.987      | 2.66x   |
| 60+60,  p=0.15        | 4.158    | 1.757       | 2.37x   |

Before this change fnx ran at ~0.83x (slower than nx). Now 2.37-2.71x FASTER.

## Score
Impact: high (2.4-2.7x faster, large absolute ms on a whole-graph centrality).
Confidence: high (integer-derived → bit-exact, 90-case golden + 432 tests).
Effort: low (single Python override, no rebuild). → Score >= 2.0.
