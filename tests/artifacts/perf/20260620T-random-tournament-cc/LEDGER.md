# Perf WIN (code-only) — random_tournament de-delegation (br-r37-c1-tournrandgen)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/tournament.py`
- DISK-LOW turn: code-only, NO cargo. Parity + conformance via existing install.

The create_py_random_state RNG-reproduction lever (proven across 4 bipartite RNG
generators) extends to tournament.random_tournament. nx flips one coin per distinct
pair in combinations(range(n), 2) order (orient u->v if r<0.5 else v->u) and builds
nx.DiGraph(edges) (node order = edge appearance). Reproduce the exact lazy draw
sequence (zip(pairs, coins)) + edge construction directly, skipping nx build +
_from_nx_graph.

## Parity (existing install, no build)
- 5000 seeds, n in 0..29: byte-exact node order, edge order, graph attrs, DiGraph
  type. n=1 -> empty (matches nx). 0 mismatches.
- pytest -k tournament: 612 passed.

## Perf
BENCH DEFERRED (disk-low). Win = skip nx build + _from_nx_graph. Measure when disk recovers.

## Follow-up (other submodule RNG generators)
swap.double_edge_swap / directed_edge_swap (RNG swap loop with rejection),
smallworld.random_reference / lattice_reference (swap-based randomisation) — more
involved; same create_py_random_state lever applies.
