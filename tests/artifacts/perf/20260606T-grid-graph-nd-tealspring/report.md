br-r37-c1-edmwo: native n-D grid graph kernel

Target
- Profile-backed bead: `grid_graph([8,8,8])` and `hypercube_graph(n)` were slower because NetworkX-style n-D grid construction rebuilt every product edge through Python.
- Alien primitive class: structural kernel replacement / zero-copy framing of the constructor surface, not a loop tweak. The Python graph builder now delegates integer-axis products to a Rust bulk constructor.

Lever
- Expose `_fnx.grid_graph_native(dimensions, periodic)` and register it in the generators module.
- Preserve NetworkX observable ordering by using the existing Rust `Graph::grid_nd` product-state implementation and Python int/tuple display keys.
- Keep iterable/custom axes on the Python parity path.

Proof
- Golden proof: `GOLDEN_SHA256 bb4bf06c5b0bef46366851ad556801f5cd55655ba15de6b297fe0c75dca4dfa8`, 13 cases.
- Focused pytest: 14 generator parity tests passed, including grid_2d, n-D grid/hypercube, Kneser, fallback axes, mutation, and pickle.
- Isomorphism constraints: node order, edge order, adjacency neighbor order, periodic wrap order, tuple/int key type, mutation semantics, and pickle output stayed aligned with NetworkX. No RNG or floating-point behavior is involved.
- Baseline proof attempted before the lever exposed an existing periodic-order defect in the fallback path; the after proof is the accepted golden.

Benchmark
- Baseline hyperfine: fnx grid_8_8_8 310.4 ms, fnx hypercube_10 349.2 ms, fnx hypercube_13 807.7 ms.
- After hyperfine: fnx grid_8_8_8 350.8 ms, fnx hypercube_10 381.7 ms, fnx hypercube_13 462.1 ms. Process startup/import noise dominates the smaller cases.
- Same-install forced-fallback comparison:
  - grid_8_8_8: 0.006832s -> 0.000684s, 9.99x
  - hypercube_10: 0.034028s -> 0.002936s, 11.59x
  - hypercube_13: 0.404318s -> 0.038556s, 10.49x
- cProfile: forced fallback 50x grid_8_8_8 took 0.488s with 67,200 `Graph.add_edge` calls; native 50x took 0.036s with the work inside `_fnx.grid_graph_native`.

Score
- Impact 4, confidence 5, effort 2 => Score 10.0. Keep.

Quality Gates
- `rch exec -- cargo check -p fnx-classes --all-targets`
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- `cargo fmt --check`
- `rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
- `ubs crates/fnx-classes/src/lib.rs crates/fnx-python/src/generators.rs`
- `ubs tests/artifacts/perf/20260606T-grid-graph-nd-tealspring/grid_graph_nd_perf.py`
