# DiGraph Edges Native Guarded Iterator

Bead: `br-r37-c1-04z53.9116`

Workload: `list(DiGraph.edges())` on
`DiGraph(gnp_random_graph(n=2000, p=0.01, seed=7, directed=True))`, 100 loops.

## Baseline

Profile-backed residual after the prior index-based `_native_edges_no_data` pass:

- Golden SHA: `af3fd33565aae84c1dc0237b9125a076b3d3b531c33a87e153a0e5822494e203`
- `rch` hyperfine loop100: FNX `2.111 s +/- 0.039 s`, NetworkX `1.542 s +/- 0.044 s`
- Gap: NetworkX `1.37x` faster
- cProfile: `_FailFastEdgeIterator` generator frame `0.492 s / 100`; `_native_edges_no_data` `0.314 s / 100`

## Rejected Micro-Lever

A packed `_mutation_token` getter was tested and rejected. It preserved the golden SHA, but hyperfine
only moved `2.111 s -> 2.078 s`, inside noise, and the Python `_gen` frame regressed
`0.492 s -> 0.542 s`. No production code from that attempt is kept.

## Kept Lever

Bare no-data `_DiGraphEdgeView.__iter__` now routes the already materialized ordered edge list through
the existing Rust `DiGraphGuardedEdgeListIter`. This removes the Python generator frame from every
yield while preserving the same materialized edge order and the same `nodes_seq`/`edges_seq`
fail-fast checks in Rust.

## Benchmark

Final exact-source `rch` hyperfine:

| Engine | Baseline mean | After mean | Delta |
| --- | ---: | ---: | ---: |
| FrankenNetworkX | 2.111 s | 1.886 s | 1.12x faster |
| NetworkX | 1.542 s | 1.530 s | comparison drift only |

Gap to NetworkX: `1.37x` slower before, `1.23x` slower after.

Direct harness:

| Engine | Baseline seconds/loop | After seconds/loop | Digest |
| --- | ---: | ---: | --- |
| FrankenNetworkX | 0.0155687552 | 0.0126143869 | `af3fd33565aae84c1dc0237b9125a076b3d3b531c33a87e153a0e5822494e203` |
| NetworkX | 0.0096368510 | 0.0093235163 | `af3fd33565aae84c1dc0237b9125a076b3d3b531c33a87e153a0e5822494e203` |

Profile:

| Frame | Baseline | After |
| --- | ---: | ---: |
| Python `_gen` guard frame | 0.492 s / 100 | removed |
| `_native_edges_no_data` | 0.314 s / 100 | 0.329 s / 100 |
| total profiled target | 1.189 s / 100 | 0.634 s / 100 |

Score: Impact 3 x Confidence 5 / Effort 2 = 7.5.

## Isomorphism And Golden Proof

Golden SHA stayed unchanged:

`af3fd33565aae84c1dc0237b9125a076b3d3b531c33a87e153a0e5822494e203`

The proof verifies:

- exact edge order for all 40,267 edges
- node-major/successor insertion-order first and last samples
- edge mutation during iteration raises `RuntimeError: dictionary changed size during iteration`
- node mutation during iteration raises the same NetworkX error type and message

There is no floating-point or RNG surface in the changed iterator route. The graph is generated with
fixed seed `7` only to build a repeatable benchmark fixture; the committed behavior change is
deterministic and order-preserving.

## Validation

- `py_compile` for `python/franken_networkx/__init__.py` and the harness
- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`
- `cargo fmt --package fnx-python --check`
- `python -m pytest tests/python/test_graph_utilities.py -k 'edge' -q`: 128 passed, 484 deselected
- `python -m pytest tests/python/test_view_str_parity.py tests/python/test_to_edgelist_view_type.py -q`: 19 passed
- `git diff --check`
- final exact-source `maturin develop --profile release-perf --features pyo3/abi3-py310`
- UBS attempted on the two changed Python files. The normal scan was interrupted after more than 7
  minutes with no findings emitted; `timeout 240s ubs --only=python --skip-python=20 --files=... .`
  also timed out with no findings emitted. Treated as UBS tool degradation for this commit.
