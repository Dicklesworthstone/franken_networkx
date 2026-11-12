# br-r37-c1-ku655: union_all multigraph no-data keyed batch

## Target Selection

After `br-r37-c1-y0xps` landed native `symmetric_difference`, the residual sweep on current `main` (`dc89cc3b6`) showed the next operator construction-tax cluster:

| Operation | Class | FNX median | NetworkX median | Ratio |
| --- | --- | ---: | ---: | ---: |
| `intersection_all` | `MultiDiGraph` | `0.024620s` | `0.006485s` | `3.80x` |
| `compose_all` | `MultiDiGraph` | `0.059965s` | `0.015813s` | `3.79x` |
| `union_all` | `MultiDiGraph` | `0.066727s` | `0.018265s` | `3.65x` |
| `union_all` | `MultiGraph` | `0.060108s` | `0.017311s` | `3.47x` |

Profile-backed chosen target: `union_all MultiDiGraph`. Baseline cProfile for 20 calls spent `1.293s` in `_multi_add_edges_from`, `0.798s` in per-edge `add_edge`, and `0.639s` in the PyO3 `MultiDiGraph.add_edge` crossing.

## Lever

One lever only: when `union_all` receives exact `MultiGraph` or exact `MultiDiGraph` inputs with no renaming, no private NetworkX storage, disjoint node sets, and empty edge attribute dicts, collect all `(u, v, key)` edges and insert them once through the existing native `_native_add_keyed_edges_no_data` batch on a still edge-empty result.

Attribute-bearing multigraph edges fall back to the existing path. Rename and mixed graph-family paths are unchanged.

## Behavior Proof

Golden proof command: `harness_ku655.py proof union_all MultiDiGraph`.

- Exact output compared: `list(result.nodes())` and exact edge list.
- Ordering/tie-breaking: preserved from NetworkX for the harness.
- Floating point: none.
- RNG: none.
- Before SHA: `e2b55dd9fbee9b55811a7b45c6bd4ebef012dd46968730f4c07acc6b368a3d9b`.
- After SHA: `e2b55dd9fbee9b55811a7b45c6bd4ebef012dd46968730f4c07acc6b368a3d9b`.
- NetworkX SHA: `e2b55dd9fbee9b55811a7b45c6bd4ebef012dd46968730f4c07acc6b368a3d9b`.

`MultiGraph` proof also stayed equal on the same harness class.

## Benchmarks

Direct median, 20 reps:

| Class | Before | After | Speedup |
| --- | ---: | ---: | ---: |
| `MultiDiGraph` | `0.066727s` | `0.048818s` | `1.37x` |
| `MultiGraph` | `0.060108s` | `0.046949s` | `1.28x` |

Hyperfine, 10 runs, 20 `union_all MultiDiGraph` calls per run:

| Before mean | After mean | Speedup |
| ---: | ---: | ---: |
| `1.6679944024s` | `1.3334757186s` | `1.25x` |

After profile for 20 `union_all MultiDiGraph` calls:

- `_multi_add_edges_from` and per-edge `add_edge` dropped out of the hot path.
- New top frames: `_native_add_keyed_edges_no_data` `0.423s`, EdgeView materialization `0.207s`, `add_nodes_from` `0.174s`.

## Validation

- `python -m py_compile python/franken_networkx/__init__.py`: passed.
- `pytest tests/python/test_operators_conformance.py tests/python/test_operator_multikey_parity.py tests/python/test_cross_type_operators.py -q`: `61 passed`.
- `git diff --check`: passed.
- UBS: `timeout 180 ubs python/franken_networkx/__init__.py tests/artifacts/perf/20260608T-ku655-operator-residual-tealspring/harness_ku655.py tests/artifacts/perf/20260608T-ku655-operator-residual-tealspring/report.md` exited `124` after entering the Python scan, with no findings emitted before the cap.

## Score

- Impact: `2.5` (profile-backed hot path removed; target hyperfine `1.25x`, direct `1.37x`).
- Confidence: `3.0` (golden SHA parity, exact ordering proof, focused operator tests).
- Effort: `2.0`.
- Score: `3.75`.
- Verdict: kept.

## Next Reprofile Route

Reprofile after this commit. The after-profile now points to node insertion and native keyed-batch cost for `union_all`; the broader residual still includes `intersection_all MultiDiGraph` and `compose_all MultiDiGraph`, so the next pass should choose between a native intersection masked kernel and a native directed/multigraph compose fold based on fresh profiles.
