# br-r37-c1-efv3d Pass 1 Report

Scope: baseline/profile/golden only. No source edits were made by this pass.

## Exact Measurement Commands

```bash
br show br-r37-c1-efv3d --json
br list --status in_progress --json
git status --short --branch
git rev-parse HEAD
rch status
VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH rch exec -- maturin develop --release --features pyo3/abi3-py310
/data/projects/franken_networkx/.venv/bin/python tests/artifacts/perf/20260614T-dijkstra-family-boldfalcon/pass1-subagent/dijkstra_family_pass1.py --mode all --runs 31 --warmup 5 --profile-repeats 15
(cd tests/artifacts/perf/20260614T-dijkstra-family-boldfalcon/pass1-subagent && sha256sum -c golden.sha256)
hyperfine --warmup 3 --runs 10 --export-json tests/artifacts/perf/20260614T-dijkstra-family-boldfalcon/pass1-subagent/hyperfine_bench_command.json '/data/projects/franken_networkx/.venv/bin/python tests/artifacts/perf/20260614T-dijkstra-family-boldfalcon/pass1-subagent/dijkstra_family_pass1.py --mode bench --runs 7 --warmup 2 --no-write'
```

## Environment

- Git HEAD: `d3d431b2b0f6d555857709cd68c8abaf7f910f97`
- Python: `3.13.7`
- NetworkX: `3.6.1`
- Graph: seeded simple undirected weighted `Graph`, 700 nodes, 3899 edges, seed `20260614`, source `0`, target `699`, weight attr `weight`.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310` completed. Existing `fnx-python` dead-code warnings were emitted; no build error.
- Hyperfine command envelope: mean `766.7 ms`, stddev `23.1 ms`, min `723.3 ms`, max `798.1 ms` across 10 process runs.

## Before Numbers

| Workload | FNX p50 ms | NX p50 ms | FNX/NX | FNX p95 ms | NX p95 ms | Digest parity |
|---|---:|---:|---:|---:|---:|---|
| `dijkstra_path_length` | 3.055 | 1.675 | 1.82x | 6.244 | 2.726 | yes |
| `shortest_path_length(weight)` | 3.009 | 1.421 | 2.12x | 5.412 | 1.550 | yes |
| `single_source_dijkstra` | 5.004 | 2.281 | 2.19x | 10.845 | 3.610 | yes |
| `dijkstra_predecessor_and_distance` | 10.965 | 2.145 | 5.11x | 15.390 | 2.940 | yes |

## Profile Top Frames

`dijkstra_predecessor_and_distance` is the clearest residual:

- FNX profile, 15 calls: `0.416s` total.
- `__init__.py:7321 _call_networkx_for_parity`: `0.415s` cumulative.
- `__init__.py:6727 _networkx_graph_for_parity`: `0.321s` cumulative.
- `backend.py:606 _fnx_to_nx`: `0.306s` cumulative.
- NetworkX's own `weighted.py:_dijkstra`: about `0.089s` cumulative for the same 15 calls.

Other surfaces:

- `dijkstra_path_length`: dominated by native `_fnx.dijkstra_path` (`0.039s` of `0.044s` over 15 calls) plus `check_dijkstra_edge_weights_fast`.
- `shortest_path_length(weight)`: same path through `dijkstra_path_length`; no separate structural tax in this profile.
- `single_source_dijkstra`: current build reaches native `_fnx.single_source_dijkstra` (`0.045s` over 15 calls). The remaining visible wrapper costs are `_fnx_sync_attrs_to_inner` (`0.025s`), `check_dijkstra_edge_weights_fast` (`0.006s`), int coercion, and reorder.

## Golden

- Standard file checksum: `85c8b419cca4c2060fd8e8b81a766b48dd7e48daf5440172c7d26184697eaf8d  golden_outputs.json`
- Canonical golden digest: `da767cf17367e8507b920b31e2c2f98f87dce1f6a1bb9a5f42346f9b8fede091`
- Full payload digest: `a368a711f6c45e7a537cde7a906159370de114bf00d90ce074ff8eb36d6563b4`
- Verification: `sha256sum -c golden.sha256` returned `golden_outputs.json: OK`.

Coverage:

- Ordering/tie-breaking via dict item order and predecessor list order.
- Int-vs-float distance typing via normalized scalar types.
- No-path and missing-node exceptions by type and message.
- Cutoff behavior for `single_source_dijkstra` and `dijkstra_predecessor_and_distance`.
- Seeded simple weighted `Graph` scalar and predecessor workloads.
- RNG seed recorded; no randomized algorithm output expected.

## Pass 2 Target

Best single hotspot: implement an FNX-native `dijkstra_predecessor_and_distance` path for weighted simple `Graph`, preserving NetworkX predecessor dict insertion order and predecessor list order.

Reason: it has the largest ratio (`5.11x`) and largest absolute p50 delta (`+8.82 ms`). The profile is not ambiguous: most FNX time is conversion and parity fallback (`_fnx_to_nx` / `_networkx_graph_for_parity`), while NetworkX's actual Dijkstra work is much smaller. A native kernel/wrapper that emits predecessor discovery order plus distances would remove the conversion tax directly.

Risk notes for Pass 2: preserve predecessor key insertion at relaxation time, predecessor list order on ties, cutoff behavior, source and missing-node/no-path error wording, integer-vs-float distance typing, and deterministic seeded graph behavior. Directed and multigraph workloads were not needed for this Pass 1 target because the measured simple weighted `Graph` already exposes the active residual.
