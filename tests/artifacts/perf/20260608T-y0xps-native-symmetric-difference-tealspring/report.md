# br-r37-c1-y0xps: Native MultiGraph/MultiDiGraph symmetric_difference

## Target

`symmetric_difference(G, H)` on exact FrankenNetworkX `MultiGraph` and
`MultiDiGraph` was still dominated by Python edge-view iteration and
`add_edges_from` result construction after the earlier native `difference`
work. Pass 28 rejected int-key micro-tuning inside `difference`; this pass uses
the broader native set-op primitive called out by the bead.

Harness:
`tests/artifacts/perf/20260608T-y0xps-native-symmetric-difference-tealspring/baseline/harness_symdiff.py`

## Baseline

Direct median-of-21 hotspot timings:

| Case | FNX | NetworkX | FNX/NX |
| --- | ---: | ---: | ---: |
| MultiDiGraph | 0.0252056400s | 0.0053153400s | 4.74x |
| MultiGraph | 0.0293711410s | 0.0054472690s | 5.39x |

Hyperfine means:

| Command | Mean | Stddev |
| --- | ---: | ---: |
| fnx-multidigraph-symdiff | 1.4055456027s | 0.0514725848s |
| nx-multidigraph-symdiff | 0.6989699426s | 0.0363316567s |
| fnx-multigraph-symdiff | 1.5445683287s | 0.0655891265s |
| nx-multigraph-symdiff | 0.6191546096s | 0.0233470548s |

## Lever

Add exact-type `_native_symmetric_difference` methods for `PyMultiGraph` and
`PyMultiDiGraph`, then route `symmetric_difference` through them after the
NetworkX-compatible multigraph and node-set checks.

The native kernel builds display-edge membership sets for both operands, emits
G-only edges first and H-only edges second, and inserts the result with keyed
native edge construction. `MultiGraph` expands membership for both undirected
orientations and falls back when row-display overrides are present.

## After

Direct median-of-21 hotspot timings:

| Case | FNX before | FNX after | Speedup |
| --- | ---: | ---: | ---: |
| MultiDiGraph | 0.0252056400s | 0.0155464910s | 1.62x |
| MultiGraph | 0.0293711410s | 0.0228408490s | 1.29x |

Hyperfine means:

| Command | Before | After | Speedup |
| --- | ---: | ---: | ---: |
| fnx-multidigraph-symdiff | 1.4055456027s | 0.9166896151s | 1.53x |
| fnx-multigraph-symdiff | 1.5445683287s | 1.1499942773s | 1.34x |

## Isomorphism proof

Golden-output bundle:

`baseline_golden=fd9e7fd4f0a557e96374ee2537f57b4847a4ba243380c3687f09e1cb99a9b8ec`

`after_golden=fd9e7fd4f0a557e96374ee2537f57b4847a4ba243380c3687f09e1cb99a9b8ec`

Per-case output SHA against NetworkX:

| Case | FNX SHA | NetworkX SHA | Exact order |
| --- | --- | --- | --- |
| MultiDiGraph | da2ad4452e92ba1763c3423b473ff4c1b4bfa8dac23b9c8c744b09da7697813c | da2ad4452e92ba1763c3423b473ff4c1b4bfa8dac23b9c8c744b09da7697813c | yes |
| MultiGraph | 788e924b61cee40bc29d25ab46fc9844431bbf14b511bd280c368f5325ef3dd9 | 788e924b61cee40bc29d25ab46fc9844431bbf14b511bd280c368f5325ef3dd9 | yes |

Ordering and tie-breaking are preserved by using the same wrapper contract:
G-only edges in G iteration order, then H-only edges in H iteration order, with
display-key equality resolved through the existing PyO3 display-key lookup. The
result preserves G node order and carries empty attrs, matching the existing
set-op wrapper. Floating-point and RNG surfaces are not used.

## Validation

- `rustfmt --edition 2024 --check crates/fnx-python/src/lib.rs crates/fnx-python/src/digraph.rs`
- `python3 -m py_compile python/franken_networkx/__init__.py .../baseline/harness_symdiff.py`
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `pytest tests/python/test_setops_order_parity.py -q`: 17 passed
- `pytest tests/python/test_operator_multikey_parity.py tests/python/test_multigraph_diff_parallel_edges_parity.py tests/python/test_graph_operator_involutions.py tests/python/test_graph_operators_parity.py -q`: 65 passed
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
- `git diff --check` on the touched source/artifact paths
- `ubs` on touched Rust files and harness exited 0 with no critical findings; the large Python wrapper scan hit the known 180s timeout without emitted findings.

## Verdict

KEEP. Score = `(Impact 4 * Confidence 4) / Effort 3 = 5.33`.

Next primitive: reprofile the operator residual and attack native
`intersection` or native `compose_all` / `union_all` folding, not another
`difference` key-lookup micro-tune.
