# br-r37-c1-04z53.64: cubic k_components certificate

## Target

Fresh profile after the hypercube pass showed
`fnx.k_components(fnx.generalized_petersen_graph(10, 2))` still delegating
through `_call_networkx_for_parity` into NetworkX's `all_node_cuts` machinery.
The baseline cProfile recorded 1,327,299 calls in 0.448s, with cumulative time
dominated by `k_components -> _call_networkx_for_parity -> nx.k_components`.

## Lever

One lever: add a bounded simple-cubic certificate. For exact simple `Graph`
inputs with no self-loops, `flow_func is None`, `m = 3n/2`, and `5 <= n <= 128`,
the fast path builds adjacency sets and proves 3-vertex-connectivity by checking
connectivity after removing every single vertex and every vertex pair. A cubic
graph has vertex connectivity at most 3 by degree; the pair-removal proof raises
the lower bound to 3, so the whole graph is the sole 3-, 2-, and 1-component.

Custom `flow_func`, disconnected cubic graphs, non-cubic graphs, larger graphs,
and graphs with a one- or two-vertex cut delegate to NetworkX parity.

## Behavior Proof

- Golden proof SHA unchanged:
  `266c6e41de09f8ecb446f9ecdd44048425fe71613c8c2796c2083fa528dba236`.
- Covered cases: Petersen, generalized Petersen `(7,2)`, `(8,3)`, `(10,2)`,
  custom flow sentinel delegation, and a cubic graph with a real two-vertex cut.
- Ordering/tie-breaking: dict key order remains `[3, 2, 1]`, with one set
  component per key for certified graphs.
- Floating point: not applicable.
- RNG: not applicable.

## Benchmark

RCH-wrapped hyperfine target:

```text
python3 -c "import franken_networkx as fnx; g=fnx.generalized_petersen_graph(10,2); fnx.k_components(g)"
```

- Baseline hyperfine mean: `0.68786512634s`.
- After hyperfine mean: `0.33990868726s`.
- Process-envelope speedup: `2.02x`.

Direct harness means:

- `gp_10_2`: `0.14077810619s -> 0.00111064403s` (`126.75x`).
- `gp_8_3`: `0.06633228639s -> 0.00063395561s` (`104.63x`).
- `gp_7_2`: `0.04739396784s -> 0.00048966857s` (`96.79x`).
- `petersen`: `0.01886984261s -> 0.00036542579s` (`51.64x`).

## Score

Impact `4.5` x confidence `5.0` / effort `1.0` = `22.5`.
