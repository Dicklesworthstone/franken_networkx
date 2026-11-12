# SWEEP — graph-building functions DOMINATED; gnm_random_graph 0.80x is construction-substrate-bound

- Agent: `BlackThrush` · 2026-06-21 · MEASURED (warm min-of-N, taskset -c 2)

## Dominated
ego_graph 1.82x, k_core 32.5x, k_truss 1.25x, subgraph.copy 1.52x, disjoint_union 2.0x,
cartesian_product 2.67x, complement 2.92x, to_undirected(DiGraph) 6.14x, stochastic_graph 5.37x,
line_graph(DiGraph) 4.83x. compose_all 1.05x (DIFFERENT) / 1.32x (identical) / compose 1.74x;
double_edge_swap 1.56x (isolated; copy 18.7x). The first-pass compose_all 0.70x / double_edge_swap
0.76x were HOST NOISE / gnm-build contamination — re-measured cleanly, both WIN.

## gnm_random_graph 0.80x — substrate, not a regression, not a quick win
gnm(1000,5000) fnx 0.80x across sizes (n=100/1000/3000 all ~0.80x). Byte-exact edges vs nx
(verified). The impl is already the optimized br-yrdso path: pure-Python rejection sampler
(reproduces nx's random.Random draw sequence, ~42% of time is the inherent randint loop both
sides pay) + ONE add_edges_from native batch. The gap is the CONSTRUCTION SUBSTRATE: nx's graph
is pure-Python dicts (cheap inserts); fnx's is a Rust IndexMap behind PyO3, so even the bulk
batch (~1ms/5k edges) loses to nx's pure-Python per-edge dict insert (~0.5ms) for a
construct-once-throwaway generator. The native-RNG lever (move the draw loop into Rust) is the
only real win and is flagged KNOWN-HARD in memory ("gnm RNG lever yrdso cost a session" — must
reproduce MT19937+gen_res53 byte-exact). NOT a regression: the code is the shipped batch version;
the historical "2.7x" predates this nx build / measured a different shape. Left as-is.
