# Correctness + NET perf WIN — gnm_random_graph(directed) returns fnx, native sampler (br-r37-c1-gnmdir)

- Agent: `BlackThrush` · 2026-06-21 · File: `__init__.py`
- RE-LANDS the native directed sampler deferred in 4e3def30f, now justified by holistic data.

## Why re-land (the constructor-only 0.81x was a MIRAGE)
gnm_random_graph(directed=True) was the ONLY directed generator returning an nx.DiGraph
(gnp/erdos_renyi/scale_free/random_k_out all return fnx). That nx result then taxed EVERY
downstream fnx call with an nx->fnx conversion (~1.8ms each). It silently corrupted THREE
of my own benchmark sessions (deepcopy(DiGraph) "0.96x", the whole BFS family "12-192x
slower") — all were the conversion tax, not real fnx losses (BFS family WINS 1.3-3.2x on a
real fnx.DiGraph).

## MEASURED — realistic construct-and-use workflow (gnm directed + descendants + pagerank + bfs_edges, n=2000 m=8000, warm min-8)
| path                                            | time    |
|-------------------------------------------------|---------|
| CURRENT (gnm->nx; fnx ops pay conversion)       | 38.73ms |
| FNX-NATIVE (this fix; gnm->fnx + native ops)    | 13.43ms |
| nx baseline                                     | 14.78ms |
=> fix is 2.86x faster than the current buggy behavior, and 1.06x faster than nx.
The bare constructor is ~0.81x (Python rejection loop, same as nx, + fnx batch vs nx
per-edge) but that is dwarfed by eliminating the per-downstream-call conversion tax.

## The fix
Native directed branch in the existing G(n,m) sampler: DiGraph + ORDERED edges + max_edges
= n*(n-1) + complete-case permutations(range(n),2) order. create_using stays delegated.

## Verify
- BYTE-EXACT vs nx 3000/3000 (type + edges + succ + pred adj order + nodes, incl complete);
  undirected unchanged 800/800; pytest -k 'gnm or random_graph' 184 passed.
