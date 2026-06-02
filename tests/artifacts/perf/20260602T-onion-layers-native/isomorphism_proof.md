# Isomorphism Proof: `br-r37-c1-l5es6`

## Lever

Route public `fnx.onion_layers` to the native `_fnx.onion_layers_rust` kernel instead of delegating through NetworkX conversion, while retaining the NetworkX fallback when the native helper is unavailable.

## Observable Contract

- Values: native result digest matches NetworkX digest `93affbdb8954c6f7cd29b9623caa88ec8dcd0b2df108f1acf625deee8e9485af` on BA(3000, 4), 11984 edges.
- Ordering: digest is computed from `list(result.items())`, so key order is included. Focused tests also compare `list(nx_result.items()) == list(fnx_result.items())`.
- Errors: wrapper rejects directed graphs, multigraphs, and self-loop inputs before native dispatch, matching the NetworkX public contract.
- Views and input coercion: focused tests cover subgraph views and nx-typed graph input.

## Tie-Breaks

The Rust kernel sorts each layer by `(degree, insertion index)`, reproducing NetworkX's stable `sorted(degrees, key=degrees.get)` behavior. This preserves dict insertion order for equal-degree nodes.

## Floating Point

No floating-point arithmetic is introduced by the wrapper route. Layer IDs are integers.

## RNG

No library RNG path changes. Benchmark graph generation uses fixed seed `11` only for reproducible measurement.

## Golden Outputs

- Fallback digest: `93affbdb8954c6f7cd29b9623caa88ec8dcd0b2df108f1acf625deee8e9485af`
- Native digest: `93affbdb8954c6f7cd29b9623caa88ec8dcd0b2df108f1acf625deee8e9485af`
- Upstream NetworkX digest: `93affbdb8954c6f7cd29b9623caa88ec8dcd0b2df108f1acf625deee8e9485af`

## Verification

- `rch exec -- .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_onion_layers_native_parity.py tests/artifacts/perf/20260602T-onion-layers-native/bench_onion_layers_route.py`: passed.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_onion_layers_native_parity.py -q`: 66 passed.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_fnx_to_nx_bulk_conversion_parity.py::test_onion_layers_matches_networkx -q`: 1 passed.
- `rch exec -- cargo fmt --package fnx-python --check`: passed.
- `rch exec -- cargo check -p fnx-python --all-targets`: passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`: passed.
