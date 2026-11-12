# br-r37-c1-f61lr native Johnson CSR negative-integer DiGraph pass

## Target

Profile-backed target: `franken_networkx.johnson(DiGraph, weight="weight")`
on deterministic string-key DAGs with integer negative weights and no negative
cycles. Baseline profile showed Python routing through NetworkX Johnson:
`_call_networkx_for_parity -> networkx.algorithms.shortest_paths.weighted.johnson`,
with NetworkX Dijkstra/reweight callback dominating the run.

## Lever

One lever: add a native Rust `johnson_path_directed` route for exact `DiGraph`
inputs whose fast Python-side scan reports finite numeric weights with at least
one negative edge, then syncs edge attrs and requires all weights to be integer
typed before dispatch. Other cases still delegate to NetworkX Johnson.

Implementation:

- Bellman-Ford potentials over the directed CSR with an implicit zero-weight
  super-source.
- One CSR reweighting pass using signed edge weights.
- Per-source Dijkstra over the reweighted CSR, preserving heap sequence
  tie-breaks and inner dict finalize order through the existing path emitter.

## Behavior proof

- Golden output SHA stayed identical:
  `3f6d69617e35d86e63f976ce41888d984ba0adf56c3293bfdf0b70a354301e55`.
- Target digest parity stayed identical:
  - `negative_dag_220`: `2944c5f4ed871d1b7af7bf5ef9832cc3eeb361002425d1badb7aa7545de4f688`
  - `negative_dag_360`: `1b97b5af04cd3ec917bc2c0c0939f8db03b167eb0aa6ac75d22ee77da54c885e`
- Ordering is preserved by iterating `nodes_ordered()` for outer rows and by
  emitting inner rows in Dijkstra heap-finalize order.
- Tie-breaking is preserved for the routed surface by strict-improvement
  predecessor updates and the existing FIFO heap sequence counter.
- Floating-point behavior is scoped to integer weights only; non-integer and
  nonfinite weights remain delegated. RNG is not used.
- Negative-cycle behavior is preserved by returning `NetworkXUnbounded`.

## Timing

Baseline artifacts were captured before the lever in this directory.

| Case | Baseline mean | Candidate mean | Speedup | Digest |
| --- | ---: | ---: | ---: | --- |
| `negative_dag_220` | 0.0714955768s | 0.0597166742s | 1.197x | unchanged |
| `negative_dag_360` | 0.2199934587s | 0.1856730550s | 1.185x | unchanged |

Candidate profile for `negative_dag_360`: 22 Python calls in 0.184s, with
0.175s inside `{built-in method franken_networkx._fnx.johnson_path_directed}`.
The previous NetworkX callback stack is no longer on the hot path.

Score: Impact 3 x Confidence 4 / Effort 2 = 6.0.

## Validation

- `rch exec -- cargo check -p fnx-python --lib`: pass on `vmi1227854`.
- `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`:
  pass on `ovh-a`; candidate extension artifact SHA
  `a28c5b17ee7d17c65732cb1acae09d3aff8537a21c1e41f2d4e4d5b109c0fee6`.
- `python3 -m py_compile` for Python package and harness files: pass.
- Focused pytest with candidate extension preloaded:
  - `tests/python/test_johnson_inner_dict_order_parity.py`
  - `tests/python/test_shortest_path.py -k johnson`
  - `tests/python/test_shortest_path_algorithms.py::TestJohnson`
  - total: 12 passed, 73 deselected.
- `git diff --check`: pass.

Known validation caveats:

- `cargo fmt --check -p fnx-algorithms -p fnx-python` still fails on broader
  pre-existing Rust formatting drift outside this lever.
- `rch exec -- cargo clippy -p fnx-python --lib -- -D warnings` is blocked by
  pre-existing `fnx-generators` unused-return warnings.
- `ubs` on the five relevant source/harness files timed out after 90 seconds
  without producing findings.
