# br-r37-c1-1bcb7 shortest_simple_paths conversion bypass

## Target

`franken_networkx.shortest_simple_paths` delegated through
`_call_networkx_for_parity`, which first converted the full FNX graph into a
NetworkX graph for every call. The kept lever runs NetworkX's undecorated Yen
generator directly on FNX `Graph`/`DiGraph` objects. Multigraphs keep the old
decorated parity fallback because the undecorated callable skips NetworkX's
multigraph rejection decorator.

No path algorithm, tie-break policy, weight handling, or generator contract was
reimplemented. The lever removes only the fnx->nx conversion layer.

## Baseline and profile

Baseline was captured after an rch release rebuild:

```text
rch exec -- maturin develop --release --features pyo3/abi3-py310
rch exec -- hyperfine --warmup 3 --runs 10 --export-json baseline_hyperfine.json \
  'python3 shortest_simple_paths_bench.py bench --impl fnx --case path_2000_first1 --loops 20' \
  'python3 shortest_simple_paths_bench.py bench --impl direct --case path_2000_first1 --loops 20' \
  'python3 shortest_simple_paths_bench.py bench --impl nx --case path_2000_first1 --loops 20'
```

Baseline profile on `path_2000_first1` showed `_call_networkx_for_parity`
inside the public FNX generator: 0.195 s cumulative in a 0.261 s / 10-loop
profile. The direct-on-FNX candidate removed that frame and measured 0.128 s in
the same 10-loop profile.

## Behavior proof

Golden rows compare current FNX public output with the direct-on-FNX candidate
for:

- path graph first path
- cycle graph first two paths
- weighted diamond ordering
- random GNP first three paths
- missing source
- missing target
- no path
- multigraph rejection

Baseline and after golden SHA:

```text
6f656edb6bb0bb333c94d6381beff5f1106d409a3c00602741852a0e5f831f88
```

`compare` passed before and after the source change. The public API remains a
real generator, and exceptions from NetworkX's undecorated generator are passed
through `_raise_translated_networkx_exception`.

## After benchmark

After the source change:

| Case | Baseline mean | After mean | Ratio |
| --- | ---: | ---: | ---: |
| path_2000_first1 x20 | 0.558364 s | 0.370417 s | 1.51x |

The after FNX mean is close to the same-worker NetworkX mean of 0.336757 s.
The after profile no longer contains `_call_networkx_for_parity`; the remaining
hot path is NetworkX's `_bidirectional_pred_succ` over FNX adjacency.

Score: Impact 3 x Confidence 4 / Effort 2 = 6.0, so the lever is kept.

## Validation

```text
.venv/bin/python -m py_compile python/franken_networkx/__init__.py shortest_simple_paths_bench.py
cargo fmt -p fnx-python --check
rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets
rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings
RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest \
  tests/python/test_shortest_simple_paths_msg_parity.py \
  tests/python/test_simple_paths_conformance.py \
  tests/python/test_traversal_generator_parity.py::test_shortest_simple_paths_yields_lazily \
  tests/python/test_astar_yen.py::TestShortestSimplePaths \
  tests/python/test_simple_paths_module_parity.py -q
```

Focused pytest result: 349 passed.

UBS note: targeted UBS on `python/franken_networkx/__init__.py` and the harness
was interrupted after more than 10 minutes with no findings emitted beyond the
startup banner. The interruption is recorded in `ubs_touched.exit` as 130.
