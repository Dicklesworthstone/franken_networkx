# Data-Key EdgeView Endpoint-Index Keep

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
| edges | 11.484653 | 2.628080 | 4.370x | 11.046103 | 2.972606 |
| edges_data_true | 4.072532 | 5.238467 | 0.777x | 5.180882 | 5.758050 |
| edges_data_w | 17.264377 | 5.715240 | 3.021x | 19.108893 | 5.769036 |
| out_edges_data_true | 0.539828 | 5.066846 | 0.107x | 0.549977 | 5.082890 |
| edges_data_view_w | 16.305198 | 5.913678 | 2.757x | 16.307685 | 5.929338 |

## Hyperfine

| Command | Mean s | Median s |
| --- | ---: | ---: |
| `env PYTHONPATH=/data/projects/.scratch/franken_networkx-2a00r-baseline-20260614T2318/python .venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which fnx --case edges_data_w --loops 5 --warmup-calls 2` | 0.543889 | 0.541835 |
| `env PYTHONPATH=/data/projects/franken_networkx/python .venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which fnx --case edges_data_w --loops 5 --warmup-calls 2` | 0.507879 | 0.506202 |
| `env PYTHONPATH=/data/projects/.scratch/franken_networkx-2a00r-baseline-20260614T2318/python .venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which fnx --case edges_data_view_w --loops 5 --warmup-calls 2` | 0.533634 | 0.536457 |
| `env PYTHONPATH=/data/projects/franken_networkx/python .venv/bin/python tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py loop --which fnx --case edges_data_view_w --loops 5 --warmup-calls 2` | 0.517079 | 0.514288 |

## Profile Evidence

Target-only cProfile for `edges(data="w")` moved `_native_edges_data_key`
from `0.577s` to `0.467s` over the same 40 calls. The guard generator frame
remained effectively flat (`0.191s -> 0.195s`), so the measured win is inside
the native data-key materializer.

```text
       40    0.467    0.012    0.467    0.012 {method '_native_edges_data_key' of 'franken_networkx.DiGraph' objects}
{"cumtime": 0.19475673200000002, "filename": "/data/projects/franken_networkx/python/franken_networkx/__init__.py", "function": "_gen", "line": 439, "primitive_calls": 1600040, "total_calls": 1600040, "tottime": 0.19475673200000002}
```

## Isomorphism Obligations

- Ordering: preserve byte-identical node-major/successor-insertion edge order for all five consumers.
- Tie-breaking: N/A beyond insertion order.
- Floating point: N/A.
- RNG: N/A, deterministic graph.
- Guard behavior: preserve FNX current `RuntimeError("dictionary changed size during iteration")` on structural node/edge token changes with `guard_edge_count=True`; preserve attr-only updates as non-structural.

## Opportunity Score

- Kept single lever: route exact-`DiGraph` `_native_edges_data_key` through
  cached node-key objects when successor display overrides are absent, preserving
  the live Python dict value lookup for `attrs.get(data, default)`.
- Impact: `2` (`data="w"` consumers only, but still the dominant residual for
  that path).
- Confidence: `3` (direct timing, target profile, and target hyperfine all move
  in the same direction; process-level hyperfine is partially startup-bound).
- Effort: `1` (one guarded branch in one native materializer).
- Score: `6.0`; keep.

## Residuals

- `_FailFastEdgeIterator` still dominates common guarded drains.
- `edges(data="w")` still trails NetworkX in this corpus, so the next pass
  should attack the value lookup/tuple materialization itself rather than the
  endpoint key hash path.
