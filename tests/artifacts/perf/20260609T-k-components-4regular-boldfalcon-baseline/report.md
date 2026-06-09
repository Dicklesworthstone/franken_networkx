# br-r37-c1-04z53.65: 4-regular k_components certificate

## Target

Post-pass profiling after the cubic certificate showed that simple 4-regular
graphs still delegated to NetworkX's `all_node_cuts` machinery:

```text
fnx.k_components(fnx.random_regular_graph(4, 24, seed=5))
```

Baseline cProfile recorded 4,237,213 calls in 1.434s, dominated by
`k_components -> _call_networkx_for_parity -> nx.k_components -> all_node_cuts`.

## Lever

One lever: add a bounded simple 4-regular certificate. For exact simple `Graph`
inputs with no self-loops, `flow_func is None`, `m = 2n`, and `6 <= n <= 64`,
the fast path builds adjacency sets and proves 4-vertex-connectivity by checking
connectivity after removing every single vertex, every vertex pair, and every
vertex triple.

For a 4-regular simple graph, vertex connectivity is at most the minimum degree
4. The triple-removal proof establishes the lower bound `kappa(G) >= 4`, so the
whole graph is the sole 4-, 3-, 2-, and 1-component.

Custom `flow_func`, disconnected graphs, non-4-regular graphs, larger graphs,
and graphs with a <=3 vertex cut delegate to NetworkX parity.

## Behavior Proof

- Golden proof SHA unchanged:
  `603e20ff482a60893491c8da838eb0441eee45df1b8b52af2770c829659d8b93`.
- Covered cases: `random_regular_graph(4,18,seed=3)`,
  `random_regular_graph(4,24,seed=5)`, custom flow sentinel delegation, and a
  4-regular graph with a real two-vertex cut.
- Ordering/tie-breaking: dict key order remains `[4, 3, 2, 1]`, with one set
  component per key for certified graphs.
- Floating point: not applicable.
- RNG: seeded graph construction only; output RNG surface not applicable.

## Benchmark

RCH-wrapped hyperfine target:

```text
PYTHONPATH=python python3 -c "import franken_networkx as fnx; g=fnx.random_regular_graph(4,24,seed=5); fnx.k_components(g)"
```

- Baseline hyperfine mean: `0.81379497636s`.
- After hyperfine mean: `0.31877177632s`.
- Process-envelope speedup: `2.55x`.

Direct harness means:

- `rr_4_24_seed5`: `0.48761782760s -> 0.01567573820s` (`31.11x`).
- `rr_4_18_seed3`: `0.27609503102s -> 0.00441309400s` (`62.56x`).

## Score

Impact `5.0` x confidence `4.5` / effort `1.0` = `22.5`.
