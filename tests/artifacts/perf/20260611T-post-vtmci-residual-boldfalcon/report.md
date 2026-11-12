# br-r37-c1-8jvq1

## Target

Post-`br-r37-c1-vtmci` residual profiling on current pushed `main`
(`1d3ab1332`) rechecked `random_regular_graph(8, 1500, seed=12345)`.

FNX was already faster than NetworkX, but the profile still showed a large
internal construction bridge:

- Direct FNX median: `0.005828665s`
- Direct NetworkX median: `0.006823625s`
- RCH hyperfine FNX mean: `0.733227604s`
- RCH hyperfine NetworkX mean: `1.042588569s`
- cProfile over 160 FNX calls: `1.026s` total, with
  `random_regular_graph` `0.985s`, `add_edges_from` `0.715s`,
  `_try_add_edges_from_batch` `0.544s`, and
  `_fnx.random_regular_edges_pyset` `0.130s`

## Alien Primitive

Narrow zero-copy/batched native construction at the generator boundary:
replace the Python `Graph.add_edges_from(PySet)` bridge with a direct native
`PyGraph` builder while preserving the current CPython set-order edge payload.

Proof obligations:

- Exact random seed behavior for the guarded integer seed path.
- Exact output digest `cac80aef6f181434007d93ef151d69b54867433c4b54c30c76a3c24f3e55bf24`.
- Same node count and edge count as NetworkX.
- Same node and adjacency order as the current FNX/NetworkX proof harness.
- Fallback unchanged for non-default `create_using`, non-int seed objects, bools,
  and oversized stub tapes.

## Lever Tried

Rejected candidate: keep the existing native insertion-order generator, build a
CPython `PySet` to recover exact set iteration order, then insert those edges
directly into a fresh Rust `Graph` and return it through `report_to_pygraph`.

This removed the visible Python `add_edges_from` bridge but retained PySet
construction and iteration inside the native function.

## Proof

Candidate proof passed:

- `all_match`: `true`
- FNX digest: `cac80aef6f181434007d93ef151d69b54867433c4b54c30c76a3c24f3e55bf24`
- NetworkX digest: `cac80aef6f181434007d93ef151d69b54867433c4b54c30c76a3c24f3e55bf24`
- Nodes: `1500`
- Edges: `6000`

## Rebench

Rejected. The candidate did not clear Score >= 2.0 and regressed the primary
same-run timing envelope.

| Metric | Baseline | Candidate | Result |
|---|---:|---:|---:|
| Direct FNX median | 5.828665 ms | 6.341724 ms | 0.92x |
| Direct FNX mean | 6.968462 ms | 6.452003 ms | 1.08x |
| RCH hyperfine FNX mean | 733.227604 ms | 913.546205 ms | 0.80x |
| cProfile total, 160 calls | 1.026 s | 0.912 s | 1.12x |
| Python add_edges bridge | 0.715 s | removed | shifted |
| New native direct builder | N/A | 0.781 s | too expensive |

The profile shift explains the rejection: the candidate removed
`add_edges_from`, but the native builder paid too much for CPython set
materialization plus re-iteration and did not improve the measured command.

## Gates

- `rustfmt --edition 2024 --check crates/fnx-python/src/generators.rs`: PASS
- `python -m py_compile python/franken_networkx/__init__.py` via project venv: PASS
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: PASS with pre-existing warnings
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: PASS with pre-existing warnings
- `pytest tests/python/test_classic_generators.py tests/python/test_degree_sequence_generators_conformance.py -q -k 'random_regular or native_random_generators_do_not_fallback'`: `23 passed, 291 deselected`

## Verdict

REJECTED / no production code kept, Score `0.0`.

Next route: do not repeat the PySet-reification family. The deeper primitive is
a CPython-set-order emulator or certificate that produces the final graph order
without constructing and re-iterating a Python set, followed by an adversarial
hash/order proof. Target ratio: at least `1.25x` over the current FNX direct
median and a non-regressing RCH hyperfine envelope.
