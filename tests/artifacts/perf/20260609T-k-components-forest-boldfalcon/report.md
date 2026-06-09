# br-r37-c1-1m567 - k_components forest lattice

## Target

After the complete-graph and simple-cycle shortcuts, forest families still
delegated to NetworkX Moody-White machinery. `star_graph(4999)` was the
profile-backed target:

- Baseline profile: 481,429 calls in 0.285 s for one `star5000` call.
- Top cumulative path: `k_components` -> `_call_networkx_for_parity` ->
  NetworkX `k_components` -> thousands of subgraph/biconnected-component
  constructions.

## Lever

Use a graph-structure certificate from native component data:

- strict `fnx.Graph`,
- no self-loops,
- `m <= n - 1`,
- connected components from the native component iterator,
- forest iff `m == n - component_count`.

For forests, the k-component lattice is closed form: only `k=1` exists, and
NetworkX omits singleton connected components. This preserves component order,
set/list shape, and flow-function behavior while avoiding NetworkX conversion
and Moody-White recursion.

## Proof

Harness: `harness_forest_k_components.py proof`

- Baseline proof SHA256: `9c60b7c15568f200a2dfe9c488b75a83ffd5cdc49967e51fcfc611586bd1e248`
- After proof SHA256: `9c60b7c15568f200a2dfe9c488b75a83ffd5cdc49967e51fcfc611586bd1e248`
- Cases: empty graph with two isolated nodes, path, star, forest with isolated
  singleton, two disconnected paths, triangle-tail delegate, self-loop delegate.
- Ordering/tie-breaking: connected-component order preserved; singleton
  components omitted exactly like NetworkX.
- Floating point: N/A.
- RNG: N/A.

## Benchmarks

All process timings were run through `rch exec -- hyperfine`.

| Case | Before | After | Delta |
| --- | ---: | ---: | ---: |
| `star5000` x20, mean | 8.225 s +/- 2.179 s | 2.694 s +/- 2.744 s | 3.05x faster |
| `star5000` x20, median | 7.288 s | 1.252 s | 5.82x faster |
| NetworkX comparator x20, mean | 5.223 s +/- 2.207 s | 2.694 s +/- 2.744 s | 1.94x faster than upstream |
| NetworkX comparator x20, median | 6.066 s | 1.252 s | 4.84x faster than upstream |

The after process benchmark is noisy because graph construction and interpreter
startup dominate once the algorithmic path is reduced to native component
primitives. A direct in-process sanity loop on already-built `star5000` graphs
recorded patched fnx x20 median `0.01366 s` versus genuine NetworkX x20 median
`1.11787 s`, an 81.8x algorithmic-path speedup.

## Gates

- `pytest tests/python/test_tree_kcomponents_assortativity_conformance.py tests/python/test_collection_container_type_parity.py -q`
  - `94 passed, 3 warnings`
  - warnings are existing assortativity NaN parity warnings in fnx/NetworkX.
- `python -m py_compile python/franken_networkx/__init__.py tests/python/test_tree_kcomponents_assortativity_conformance.py tests/artifacts/perf/20260609T-k-components-forest-boldfalcon/harness_forest_k_components.py`
  - pass
- `ubs tests/python/test_tree_kcomponents_assortativity_conformance.py tests/artifacts/perf/20260609T-k-components-forest-boldfalcon/harness_forest_k_components.py`
  - pass, no critical/warning findings
- `timeout 180s ubs python/franken_networkx/__init__.py`
  - timed out with no emitted findings; known scanner/runtime limitation on this large wrapper file
- `rch exec -- cargo check -p fnx-python --all-targets`
  - pass; existing `fnx-generators` unused-must-use warnings remain
- `cargo fmt -p fnx-python --check`
  - fails on pre-existing untouched Rust formatting drift in `crates/fnx-python/src/{algorithms.rs,digraph.rs,lib.rs,readwrite.rs}`
- `rch exec -- cargo clippy -p fnx-python --all-targets --no-deps -- -D warnings`
  - fails on pre-existing untouched `collapsible_if` lints in `digraph.rs` and `lib.rs`, plus existing `fnx-generators` warnings

## Score

Impact 4 x confidence 4 / effort 1 = 16. Keep.
