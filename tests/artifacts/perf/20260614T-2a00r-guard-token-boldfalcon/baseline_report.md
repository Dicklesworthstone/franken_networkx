# Guard Token EdgeView Baseline

Bead: `br-r37-c1-2a00r`

## Workload

- DiGraph nodes: `5000`
- DiGraph edges: `40000`
- Deterministic directed circulant insertion order, spans `1..8`, integer edge attr `w`.
- Timed consumers: `list(DG.edges())`, `list(DG.edges(data=True))`, `list(DG.edges(data="w"))`, `list(DG.out_edges(data=True))`, `list(DG.edges.data("w"))`.

## Golden

- Golden bundle SHA: `7f1f79e081e71ab0e4030308a1df76f3419b7a14bc8ee8a3d58ef2aa693aeeea`
- Golden file SHA: `6b4ccd83d4948aaa685270ba125eb6b0a250d676a4bf7f8dc5c64d96e4613684`
- Edge outputs byte-equal FNX vs NetworkX: `True`
- Compared structural edge mutations match NetworkX: `True`
- FNX current node/edge guard obligations pass: `True`

## Direct Timing

| Case | FNX median ms | NX median ms | FNX/NX median | FNX mean ms | NX mean ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| edges | 21.289696 | 4.827199 | 4.410x | 23.639112 | 5.105327 |
| edges_data_true | 13.073435 | 8.844711 | 1.478x | 13.739387 | 9.059574 |
| edges_data_w | 50.199544 | 9.619154 | 5.219x | 48.059707 | 10.630494 |
| out_edges_data_true | 0.708348 | 12.991989 | 0.055x | 0.708861 | 13.654571 |
| edges_data_view_w | 30.261039 | 18.245394 | 1.659x | 39.511950 | 21.232812 |

## Hyperfine

| Command | Mean s | Median s |
| --- | ---: | ---: |
| `.venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which fnx --case edges --loops 5 --warmup-calls 2` | 1.064166 | 1.029720 |
| `.venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which nx --case edges --loops 5 --warmup-calls 2` | 0.623194 | 0.598331 |
| `.venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which fnx --case edges_data_true --loops 5 --warmup-calls 2` | 0.942330 | 0.911570 |
| `.venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which nx --case edges_data_true --loops 5 --warmup-calls 2` | 0.832654 | 0.723352 |
| `.venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which fnx --case edges_data_w --loops 5 --warmup-calls 2` | 1.010927 | 0.990618 |
| `.venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which nx --case edges_data_w --loops 5 --warmup-calls 2` | 0.860578 | 0.800507 |
| `.venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which fnx --case out_edges_data_true --loops 5 --warmup-calls 2` | 0.919877 | 0.913729 |
| `.venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which nx --case out_edges_data_true --loops 5 --warmup-calls 2` | 0.732400 | 0.700173 |
| `.venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which fnx --case edges_data_view_w --loops 5 --warmup-calls 2` | 1.154411 | 1.111054 |
| `.venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which nx --case edges_data_view_w --loops 5 --warmup-calls 2` | 0.767081 | 0.719700 |

## Profile Evidence

cProfile still attributes a material share of FNX edge-view drain time to the `_FailFastEdgeIterator` generator frame. The combined profile also shows `_native_edges_data_key` as the largest frame for the `data="w"` consumers, so the hotspot has partly shifted there; the guard-token lever remains the common residual across guarded drains but will not by itself fix the native data-key materializer.

The two guarded structural-token property reads are not broken out as Python functions, but the `_gen` frame below is the loop containing the current `nodes_seq` and `edges_seq` checks.

```text
       80    0.000    0.000    0.001    0.000 /data/projects/franken_networkx/python/franken_networkx/__init__.py:414(_FailFastEdgeIterator)
       80    0.000    0.000    0.001    0.000 /data/projects/franken_networkx/python/franken_networkx/__init__.py:414(_FailFastEdgeIterator)
{"cumtime": 0.728392959, "filename": "/data/projects/franken_networkx/python/franken_networkx/__init__.py", "function": "_gen", "line": 439, "primitive_calls": 3200080, "total_calls": 3200080, "tottime": 0.728392959}
{"cumtime": 0.0008299850000000001, "filename": "/data/projects/franken_networkx/python/franken_networkx/__init__.py", "function": "_FailFastEdgeIterator", "line": 414, "primitive_calls": 80, "total_calls": 80, "tottime": 0.00045909700000000005}
```

## Isomorphism Obligations

- Ordering: preserve byte-identical node-major/successor-insertion edge order for all five consumers.
- Tie-breaking: N/A beyond insertion order.
- Floating point: N/A.
- RNG: N/A, deterministic graph.
- Guard behavior: preserve FNX current `RuntimeError("dictionary changed size during iteration")` on structural node/edge token changes with `guard_edge_count=True`; preserve attr-only updates as non-structural.

## Opportunity Score

- Proposed single lever: add one PyO3 getter returning a packed `(nodes_seq, edges_seq)` guard token for DiGraph/Graph/Multi* and make `_FailFastEdgeIterator` compare one token per yielded edge when `guard_edge_count=True`.
- Impact: `3` (all guarded edge-view drains, strongest on `edges()` and `_EdgeListWithSetAlgebra` consumers).
- Confidence: `4` (profile still lands in the guard generator and bead history isolated this residual after materialization wins).
- Effort: `2` (one Rust getter family plus one Python guard branch and focused property tests).
- Score: `6.0`; still above the `>=2.0` threshold for an implementation pass.

## Future Implementation Surface

- `python/franken_networkx/__init__.py`: `_FailFastEdgeIterator` guard capture/compare branch.
- `crates/fnx-python/src/digraph.rs`: `PyDiGraph`/`PyMultiDiGraph` combined guard-token getter.
- `crates/fnx-python/src/lib.rs`: `PyGraph`/`PyMultiGraph` combined guard-token getter if the lever is generalized to all guarded edge consumers.
