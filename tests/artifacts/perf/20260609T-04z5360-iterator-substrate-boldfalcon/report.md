# br-r37-c1-04z53.60: Graph iterator dict-key substrate

## Profile-backed target

`br-r37-c1-04z53.60` identified the remaining raw `set(G)` / `list(G)` gap as
per-element PyO3 iterator dispatch. Baseline cProfile for `set(Graph)` at
1500 nodes, 300 loops showed the Python wrapper around `Graph.__iter__` still
visible and total profile wall at 0.017 s. Direct medians:

| Case | Baseline | After | Speedup |
| --- | ---: | ---: | ---: |
| `set(G)`, 1500 nodes | 0.056667 ms | 0.016551 ms | 3.42x |
| `list(G)`, 1500 nodes | 0.047731 ms | 0.008035 ms | 5.94x |

Hyperfine, same command shape, 25 runs, 200 `set(G)` loops per process:

- baseline mean: 417.4 ms
- after mean: 312.1 ms
- process-level speedup: 1.34x

After cProfile for the same `set(G)` loop dropped to 0.008 s total. The
remaining Python frame is the existing private-override wrapper; the per-node
iteration is now CPython's C-level `dict_keyiterator`.

## One lever

Exact `Graph.__iter__` now returns an iterator over a lazy live `PyDict` mirror
of node display keys. The mirror is initialized on first iteration only. Once
initialized, node-add, node-remove, clear, integer-node fast paths, and Graph
edge-batch paths update the same dict object, so active iterators observe the
same CPython mutation semantics NetworkX gets from its `_node` dict.

No graph algorithm, edge order, node canonicalization, floating-point, or RNG
logic changed. DiGraph, MultiGraph, and MultiDiGraph keep their existing
`NodeIterator` path for a later pass.

## Behavior proof

Proof harness:
`tests/artifacts/perf/20260609T-04z5360-iterator-substrate-boldfalcon/harness_iterator_substrate.py`

Golden payloads:

- baseline proof SHA: `3e733c7e79e8fbaabb14e93090afe03df6ccfa29682c1bc8ccfd3fd287d9a547`
- after proof SHA: `7490b1f3a935c6b7ffdf609fa37d88c755fcb8cb2cc788f740d1be464387c99e`

The SHA changes intentionally because `Graph.__iter__` now reports
`dict_keyiterator` like NetworkX instead of `NodeIterator`. Node ordering,
hash-equal display behavior (`0`, `0.0`, `True`, `"0"`), edge display order,
size-changing mutation errors, clear mutation errors, and existing-edge
mutation behavior remain oracle-aligned. Same-size remove/add now follows the
NetworkX/CPython dict iterator behavior on this Python: no RuntimeError, and
the replacement key is yielded.

Artifact checksums are recorded in `proof_files.sha256`.

## Gates

- PASS: `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- PASS: focused pytest:
  `tests/python/test_review_mode_regression_lock.py -q -k 'graph_iteration or adjacency_view_iter_returns_dict_keyiterator or neighbors_successors_predecessors_return_dict_keyiterator'`
- PASS: `python -m py_compile` on the harness
- BLOCKED: `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  by pre-existing `fnx-generators` unused-must-use warnings.
- BLOCKED: `cargo fmt -p fnx-python --check` by pre-existing formatting drift
  in `algorithms.rs`, `digraph.rs`, `lib.rs`, and `readwrite.rs`.
- UBS: completed on changed files, but exits 1 on existing broad warning and
  test-security inventories in the long regression file.

## Score

Impact 4 x Confidence 5 / Effort 2 = 10.0. Keep.

## Reprofile routing

The next deeper primitive should apply the same live-dict substrate to
`DiGraph`, `MultiGraph`, and `MultiDiGraph` iteration or eliminate the remaining
private-override wrapper frame for exact graph instances.
