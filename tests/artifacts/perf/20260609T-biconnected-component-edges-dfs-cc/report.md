# perf(biconnected_component_edges): native DFS edge-stack, drop nx delegation

br-r37-c1-bcedfs

## Problem
`biconnected_component_edges` was 2.95x slower than nx: the Python wrapper
delegated to nx via `_call_networkx_for_parity` (full fnx->nx O(V+E) conversion
+ nx's algorithm). It delegated because the existing native kernel emitted
sorted *canonical* edges, but nx yields edges in DFS-traversal order with the
DFS *discovery direction* (e.g. back edge (4,2), not canonical (2,4)).

## Lever (one)
Port nx's iterative DFS edge-stack algorithm (`_biconnected_dfs`,
components=True) into a native helper `biconnected_component_edges_dfs` over an
integer adjacency list (each row in `iter(G[node])` order). It reproduces nx's
edge_stack/edge_index/low/discovery bookkeeping exactly, so component order,
intra-component edge order, and per-edge orientation are byte-identical. Wrapper
routes straight to the rebuilt native binding (keeps eager directed-raise +
generator contract).

Touched: crates/fnx-python/src/algorithms.rs (binding + DFS helper),
python/franken_networkx/__init__.py (wrapper: drop delegation).

## Proof (nx-exact)
130-case corpus: path/cycle/complete/star/barbell/lollipop (articulation points
+ multiple biconnected components), empty(0)/empty(5), self-loop + isolated
node, 120 random gnp n=0..35. **0 mismatches vs nx** (component order + edge
order + edge orientation). Generator contract preserved
(isinstance GeneratorType True); directed input raises NetworkXNotImplemented.
BCE_SHA b5dac46136b377ff3a9f4807301a20edc0a6cc746c6b0a6ee3c6648a770d55a0
pytest -k biconnected: 246 passed.

## Timing (warm min-of-8)
| case            | nx (ms) | fnx before | before ratio | fnx after | after ratio |
|-----------------|--------:|-----------:|-------------:|----------:|------------:|
| ws n=200        |  0.464  |   ~1.4     |    ~2.95x    |   0.197   |   0.42x (2.4x faster) |
| ws n=400        |  0.674  |   ~2.0     |    ~2.95x    |   0.246   |   0.36x (2.8x faster) |
| ws n=1000       |  1.916  |    —       |      —       |   0.616   |   0.32x (3.1x faster) |
| BA n=800        |  1.617  |    —       |      —       |   0.538   |   0.33x (3.0x faster) |

2.95x slower -> ~3x FASTER than nx.

## Score
Impact: high (delegation removed, 2.95x slower -> 3x faster). Confidence: high
(0/130 vs nx incl. self-loops/articulation/multi-component, 246 tests pass).
Effort: moderate (faithful DFS port). Score >> 2.0.
