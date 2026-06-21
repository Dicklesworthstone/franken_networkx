# Negative Evidence Ledger

Campaign: `br-r37-c1-04z53` no-gaps performance domination.

## 2026-06-21 Cod-B `non_edges` Native-Row Regression Recheck (`br-r37-c1-04z53`, cod-b)

Scope: fresh BOLD-VERIFY recheck of the remaining
`non_edges_sparse_undirected` public-gauntlet row after an unrelated
spanning-tree fix commit briefly carried the exact undirected native-row
`Graph.non_edges` block. Reused existing detached worktree
`/data/projects/.worktrees/fnx-bt-3` and
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; no new
`.scratch` or perf-proof worktree was created.

Profile and radical lever tested:
- Alien-graveyard / alien-artifact hypothesis: preserve NetworkX `set.pop()`
  semantics while using native node-key snapshots and raw neighbor rows, then
  try to remove one allocation layer by replacing `nodes - set(raw_neighbors)`
  with `nodes.copy(); difference_update(raw_neighbors)`.
- The copy/difference-update variant was invalid: focused order conformance
  failed `9` of `47` cases because CPython set deletion order does not match
  the `nodes - set(neighbors)` result order. It was not timed.
- The exact native-row variant preserved order but was slower than the
  restored public fallback on the same RCH worker. Current head `3f59a7f9a`
  already source-reverted the unrelated native-row block while preserving the
  spanning-tree fix.

Head-to-head timing:
- RCH worker: `vmi1153651`; requested target
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`,
  rewritten by RCH to that worker's scoped target.
- Command shape:
  `RCH_WORKER=vmi1153651 RCH_REQUIRE_REMOTE=1 AGENT_NAME=cod-b CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- env PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/.worktrees/fnx-bt-3/crates/fnx-python/benches:/data/projects/.worktrees/fnx-bt-3/python:/data/projects/.worktrees/fnx-bt-3/legacy_networkx_code/networkx cargo bench -p fnx-python --bench public_api_gauntlet -- non_edges_sparse_undirected --sample-size 10 --warm-up-time 1 --measurement-time 4`
- Setup failures not used as evidence: `ovh-a` failed before sampling because
  the remote process lacked `public_api_gauntlet` on `PYTHONPATH`; `hz2` failed
  before sampling because its Python environment lacked NumPy.

| State | FNX mean | NetworkX mean | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| restored/fallback source | `1.3427 s` | `1.3203 s` | `0.983x` | active row reproduced; non-dominating |
| exact native-row candidate | `1.4501 s` | `1.2864 s` | `0.887x` | reject; FNX regressed |

Validation and gates:
- Invalid copy/difference-update variant failed focused order guards:
  `9 failed, 38 passed`.
- Exact native-row variant passed focused order/checksum parity before timing:
  `47 passed` plus a 60-seed direct order sweep and gauntlet-fixture checksum
  match (`4829200199316911967` for both engines).
- Final restored source passed focused non-edges conformance:
  `tests/python/test_non_edges_order_conformance_guard.py` plus the two
  targeted graph-utility non-edges guards, `47 passed`.
- Final restored source also passed
  `python -m py_compile python/franken_networkx/__init__.py` and
  `git diff --check`.

Decision:
- Reject/no-ship. Do not reintroduce public native-row dispatch for undirected
  `non_edges`; the exact-order version regresses the active public row and the
  allocation-saving mutation variant breaks set-order parity.
- Current focused score for this recheck: `0` wins / `1` loss / `0` neutral.
- The remaining credible route is still consumer-fused: avoid creating public
  Python non-edge pairs at all for downstream consumers, rather than another
  public `non_edges` iterator micro-route.

## 2026-06-21 Cod-B `ubizp` MultiGraph SSSP Parent-Copy No-Ship (`br-r37-c1-04z53`, cod-b)

Scope: fresh BOLD-VERIFY revisit of the remaining `ubizp`
`MultiGraph.single_source_shortest_path` path-emission loss. Reused existing
detached worktree `/data/projects/.worktrees/fnx-bt-3` and
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; no new
`.scratch` or perf-proof worktree was created.

Profile and radical lever tested:
- Alien-graveyard / alien-artifact hypothesis: the current predecessor-table
  route still pays a Python list materialization pass after BFS. Try keeping
  BFS and path construction fused under the GIL, copying the already-built
  parent Python list and appending the discovered child immediately. This
  attempts to trade the second reconstruction pass for CPython's optimized
  `list.copy()` path.
- Implementation sketch tested in `crates/fnx-python/src/algorithms.rs`:
  native MultiGraph BFS over `mg.neighbors`, one `Vec<Option<PyObject>>` of
  parent path objects, and per-child `parent_path.copy(); append(child)` before
  inserting into the result dict.
- The source hunk was reverted after measurement. The only final source diff
  left in this session is rustfmt's wrapping normalization in the same reserved
  file.

Head-to-head timing:
- Oracle: vendored NetworkX `3.7rc0.dev0` from
  `legacy_networkx_code/networkx`, Python `3.13`, `PYTHONHASHSEED=0`,
  `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, pinned with `taskset -c 4`.
- Fixture: identical FNX/NetworkX `MultiGraph`, `1,600` integer nodes,
  `6,354` edges: parallel chain edges plus `+7` and `+37` shortcuts. Source
  node `0`; output parity asserted before every timing pass.
- Checked-in Criterion benches still do not contain this exact MultiGraph SSSP
  path-returning surface, so this pinned vendored-oracle loop remains the
  keep/reject proof path for `ubizp` path emission.

| State | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| pre-lever current source, same loop | `0.875438 ms` | `0.703192 ms` | `0.803x` | active loss reproduced |
| parent-copy candidate | `2.449591 ms` | `0.867754 ms` | `0.354x` | reject |
| restored source rerun 1, noisy host | `2.316699 ms` | `1.033589 ms` | `0.446x` | parity restored; still active loss |
| restored source rerun 2, noisy host | `1.710842 ms` | `0.825284 ms` | `0.482x` | parity restored; still active loss |

Validation and gates:
- Candidate parity matched vendored NetworkX on all `1,600` paths before
  timing; output length was `1,600`.
- Candidate `AGENT_NAME=cod-b CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-13 rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`
  passed before rejection. It emitted expected dead-code warnings because the
  old predecessor emitter became unused.
- Candidate and restored-source release installs used
  `maturin develop --release --features pyo3/abi3-py310` against the prescribed
  warm target. The first local install hit stale-artifact `E0514`; the target
  was not cleaned. Switching to `nightly-2026-06-10` matched the existing
  `beae78130` artifacts and avoided destructive cleanup.
- Restored source conformance:
  `pytest -q tests/python/test_single_source_shortest_path_parity.py tests/python/test_single_source_shortest_bfs_order_parity.py tests/python/test_exact_path_tiebreak_parity.py tests/python/test_shortest_path.py tests/python/test_shortest_path_algorithms.py tests/python/test_shortest_path_conformance_matrix.py tests/python/test_shortest_path_variants_parity.py tests/python/test_shortest_path_cross_type.py tests/python/test_multigraph_algorithms.py`
  passed: `358 passed, 5 skipped`.
- Final gates after revert: `cargo fmt --check` passed;
  `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed on
  `hz2`; `rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  passed on `hz1`.

Decision:
- Reject/no-ship. Final focused score for this attempted lever: `0` wins /
  `1` loss / `0` neutral.
- Do not repeat Python-list parent copying for MultiGraph SSSP. It increases
  GIL-held Python object churn and regresses the already-losing row.
- Next route must attack the path-output substrate itself: for example a
  lazy/fused consumer route, compact path-span representation, or API-specific
  sink that avoids public dict-of-full-list materialization when possible.

## 2026-06-21 Cod-A `stochastic_graph` Exact-MultiDiGraph Native Copy Keep (`br-r37-c1-04z53.9160`, cod-a)

Scope: fresh BOLD-VERIFY child bead for the active no-gaps campaign, focused on
the remaining exact `MultiDiGraph.stochastic_graph(copy=True)` head-to-head
loss. Reused `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`;
no new `.scratch` worktree was created.

Baseline and rejected routes:
- Pre-lever public copy rows preserved parity but lost badly against vendored
  NetworkX: n=400/e=1600 `0.321x`, n=1000/e=5000 `0.249x`.
- A normalizer-only route still paid the Python shallow-copy tax, so it stayed
  losing and was not kept.
- A fresh-topology native copy builder won only small rows but lost larger rows:
  n=400/e=1600 `1.688x`, n=1000/e=5000 `0.781x`,
  n=2000/e=10000 `1.040x`, n=4000/e=20000 `0.793x`. That source shape was
  replaced before final gates.
- A clone-plus-per-edge String-key lookup candidate improved the surface but
  still had a large-row median loss: n=4000/e=20000 `0.946x`. It was replaced
  with ordered batch mutation before final gates.

Radical lever kept:
- Alien-graveyard / alien-artifact hypothesis: do not materialize every
  `(u, v, key, attrdict)` tuple through Python, and do not rebuild multigraph
  topology from string endpoints. Sync dirty live edge attrs once, verify
  lossless Python mirrors, clone the native multigraph topology, compute source
  degrees in node-index space, and patch only the derived weight field in
  `edges_ordered_borrowed()` order.
- The storage-level `set_ordered_edge_attr_values` primitive removes the
  per-edge `DirectedEdgeKey` hash lookup from the clone path. This is the
  difference between the partial `0.946x` large-row loss and the final large-row
  wins.
- The helper returns `None` for non-lossless or nonnumeric weight cases so the
  Python wrapper preserves NetworkX-observable fallback and exception behavior.

Final gates and timing evidence:
- `cargo fmt --check` passed.
- `python3 -m py_compile python/franken_networkx/__init__.py tests/python/test_graph_operators_parity.py`
  passed.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build --release -p fnx-python --features extension-module`
  passed on RCH worker `hz2`.
- `ldd /data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`
  showed no `libpython` dependency and no missing libraries.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo check -p fnx-classes --all-targets`
  passed on RCH worker `hz1`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`
  passed on RCH worker `hz1`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo test -p fnx-classes`
  passed on RCH worker `ovh-a`: `68 passed`, `2 ignored`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo check -p fnx-python --all-targets --features extension-module`
  passed on RCH worker `hz1`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo clippy -p fnx-python --all-targets --features extension-module -- -D warnings`
  passed on RCH worker `hz1`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`
  passed on RCH worker `hz2`: `27 passed`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo test -p fnx-python --features extension-module`
  failed to link a Rust test executable on RCH worker `hz2` with undefined
  Python C API symbols. This is a PyO3 `extension-module` test-link mode issue,
  not a runtime or release-extension failure; release builds and ABI3 Rust tests
  are the valid gates above.
- Focused direct conformance preloaded
  `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` as
  `franken_networkx._fnx` and passed helper in-place, helper copy, public
  `copy=True` with dirty live edge-dict sync, source isolation, bool/missing
  weights, and nonnumeric fallback.
- Final benchmark loop used the same preloaded release extension, vendored
  NetworkX from `legacy_networkx_code/networkx`, deterministic keyed
  MultiDiGraph fixtures, and parity assertions before timing.

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| exact `MultiDiGraph.stochastic_graph(copy=True)`, n=400/e=1600 | `1.212 ms` | `3.595 ms` | `2.966x` | win |
| exact `MultiDiGraph.stochastic_graph(copy=True)`, n=1000/e=5000 | `8.620 ms` | `11.737 ms` | `1.362x` | win |
| exact `MultiDiGraph.stochastic_graph(copy=True)`, n=2000/e=10000 | `19.333 ms` | `23.239 ms` | `1.202x` | win |
| exact `MultiDiGraph.stochastic_graph(copy=True)`, n=4000/e=20000 | `46.311 ms` | `48.076 ms` | `1.038x` | win |
| exact `MultiDiGraph.stochastic_graph(copy=True)`, n=8000/e=40000 | `99.791 ms` | `102.295 ms` | `1.025x` | win |

Decision:
- Keep. Final score: `5` wins / `0` losses / `0` neutral.
- This closes the active exact `MultiDiGraph.stochastic_graph(copy=True)`
  residual. The prior n=1000/e=5000 public row moved from `0.249x` loss to
  `1.362x` win.

Do not repeat:
- Do not retry normalizer-only public paths for `copy=True`; the shallow copy
  remains the dominant tax.
- Do not retry fresh topology rebuilds for this surface; clone plus ordered
  attr mutation is faster and preserves insertion order with less graph-state
  reconstruction.
- Do not use `cargo test -p fnx-python --features extension-module` as the
  Rust unit-test gate on RCH. Use `pyo3/abi3-py310` for Rust tests and
  `extension-module` for release builds / importable `.so` timing.

## 2026-06-21 Cod-A `stochastic_graph` Exact-DiGraph Native Normalizer Keep (`br-r37-c1-04z53.9159`, cod-a)

Scope: fresh BOLD-VERIFY child bead for the active no-gaps campaign, focused on
the remaining `stochastic_graph(DiGraph)` head-to-head loss. Reused
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`; no new
`.scratch` worktree was created.

Baseline and rejected route:
- Fresh direct release probe before the source lever preserved parity but showed
  the current exact `DiGraph` route still losing: FNX median `5.080 ms` vs
  NetworkX `4.512 ms`, ratio `0.888x`, on n=1000/e=3200. The same probe showed
  `MultiDiGraph` still much worse at FNX `27.498 ms` vs NetworkX `9.993 ms`,
  ratio `0.363x`.
- A Python successor-row normalization micro-probe was rejected before editing:
  current FNX median `4.715 ms`, successor-row loop `11.088 ms`, NetworkX
  `4.879 ms`. Do not repeat this family.

Radical lever kept:
- Alien-graveyard / alien-artifact hypothesis: stop paying the Python
  `edges(data=True)` traversal and row-sum loop for exact `DiGraph`
  `stochastic_graph`. Instead, run one native PyO3 pass over the stored edge
  order, accumulate outgoing sums, and mutate the live edge-attribute dicts with
  the normalized float weight.
- The helper pre-scans all weights before mutation and returns `false` for
  nonnumeric/object/string weights so the Python fallback preserves NetworkX
  exception behavior. Missing weights and bool/int/float weights are handled
  natively.

Final gates and timing evidence:
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
  passed on RCH worker `ovh-a`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  passed on RCH worker `ovh-a`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`
  passed on RCH worker `ovh-a`: `27 passed`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  passed on RCH worker `ovh-a`.
- `cargo fmt --check` passed locally after formatting `fnx-python`.
- `python3 -m py_compile python/franken_networkx/__init__.py tests/python/test_graph_operators_parity.py`
  passed.
- Focused direct oracle loop preloaded
  `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` as
  `franken_networkx._fnx`, with `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, and
  `OPENBLAS_NUM_THREADS=1`.
- Parity matched vendored NetworkX for copy/in-place behavior, missing weights,
  bool weights, zero row sums, `MultiDiGraph` fallback, and string-weight
  exception fallback. Focused pytest was blocked by the hard-coded stale
  in-tree `_fnx.abi3.so` guard in `tests/python/conftest.py`, so the direct
  preloaded extension loop is the focused Python conformance proof.

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `stochastic_graph` exact `DiGraph`, n=400/e=1200 | `0.960064 ms` | `1.680509 ms` | `1.750x` | win |
| `stochastic_graph` exact `DiGraph`, n=1000/e=3200 | `2.682792 ms` | `4.570833 ms` | `1.704x` | win |
| `stochastic_graph` exact `DiGraph`, n=2000/e=7000 | `7.944119 ms` | `10.951245 ms` | `1.379x` | win |

Decision:
- Keep. Final score: `3` wins / `0` losses / `0` neutral.
- This flips the fresh exact-`DiGraph` `stochastic_graph` baseline from a
  `0.888x` loss into measured wins. `MultiDiGraph` remains a separate residual
  at the pre-lever `0.363x` loss and needs a different native copy/normalizer
  route.

Do not repeat:
- Do not retry Python successor-row loops for `stochastic_graph`; the measured
  micro-probe was slower than both current FNX and NetworkX.
- Do not route nonnumeric/object/string weights through the native helper; the
  fallback is required to preserve NetworkX exception semantics.
- Do not count this as a `MultiDiGraph` fix; that surface still loses and needs
  a separate native multi-edge substrate.
## 2026-06-21 Cod-B Borrowed Dirty-Key Sparse Keep (`br-r37-c1-04z53`, cod-b)

Scope: fresh BOLD-VERIFY pass on the dirty/live high-unique
`MultiDiGraph` sparse-export residual. Reused the existing detached worktree
`/data/projects/.worktrees/fnx-bt-3` and
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; no new
`.scratch` worktree was created and the shared target was not cleaned.

Radical lever kept:
- Alien-graveyard / alien-artifact hypothesis: treat the dirty edge set as a
  compact sparse delta, not as a global invalidation bit. Build one borrowed
  `(&str, &str, key)` dirty-key lookup per export, read stored Rust attrs for
  untouched edges, and cross the Python dict boundary only for exact dirty
  `G[u][v][key]` mutations.
- This is deliberately narrower than the rejected broad live-weight index and
  different from the earlier stored-attr bypass attempt: the hot loop no longer
  allocates owned `(u, v, key)` lookup tuples for clean edges in the dirty
  path, while broad dirty escapes still fall back to authoritative live attrs.

Current-source direct head-to-head:
- Oracle: vendored NetworkX `3.7rc0.dev0` from
  `legacy_networkx_code/networkx`, Python `3.13.7`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`,
  pinned with `taskset -c 4`.
- Fixture: deterministic seed `1`, `2,000` nodes, `12,000` unique keyed
  directed edges, `388` public post-construction
  `G[u][v][key]["weight"] = ...` mutations, non-integer float weights,
  default nodelist, default `weight="weight"`.
- Parity: sorted coordinate sparse payload matched for both
  `to_scipy_sparse_array` and `adjacency_matrix`; digest
  `6a308478ec5832944239b9997a05fb7af357a9edac80d494cf22e7db2e2489b1`,
  `12,000` nnz, float64 data, sum `1056934.0`.

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty high-unique 12k-edge MDG | `8.491933 ms` | `11.235742 ms` | `1.323x` | win |
| `adjacency_matrix`, dirty high-unique 12k-edge MDG | `6.873216 ms` | `11.972349 ms` | `1.742x` | win |

Validation:
- Focused sparse exporter conformance:
  `tests/python/test_to_scipy_sparse_native_weighted_parity.py` plus
  `tests/python/test_to_scipy_sparse_default_native_parity.py`: `304 passed`.
- RCH gates on final source passed before the local ABI rebuild:
  `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  and
  `cargo build --release -p fnx-python --features pyo3/abi3-py310`.
- `cargo fmt --check` passed and `ubs crates/fnx-python/src/readwrite.rs`
  reported no new critical finding for the touched source.
- Focused RCH Criterion attempts for
  `multidigraph_to_scipy_sparse_array_csr_int_weights` built the bench binary
  on workers `vmi1149989` and `vmi1152480`, then failed before sampling with
  `ModuleNotFoundError("No module named 'public_api_gauntlet'")`; these runs
  are recorded as worker Python-path failures, not keep evidence.

Decision:
- Keep. The dirty sparse residual flips to `2` wins / `0` losses / `0`
  neutral vs NetworkX on the direct vendored-oracle proof.
- Remaining active no-gaps targets are the ubizp path-returning output loss
  and the `non_edges_sparse_undirected` public boundary.

Do not repeat:
- Do not re-test broad live-weight indexing or per-edge owned dirty-key tuple
  construction for this sparse exporter. The kept shape is a borrowed dirty-set
  delta plus stored-attr fast path for untouched edges.
- If this area regresses again, the next route should be native sparse-array
  handoff or a compact numeric edge-weight mirror, not another all-edges live
  attr scan.
## 2026-06-21 Cod-A `non_edges` Exact-Int Lazy Iterator No-Ship (`br-r37-c1-04z53`, cod-a)

Scope: fresh BOLD-VERIFY follow-up on the active
`non_edges_sparse_undirected` public-gauntlet loss. Reused
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`; no new
`.scratch` worktree was created.

Radical lever tested and reverted:
- Alien-graveyard / alien-artifact hypothesis: for the measured simple
  undirected exact-int `Graph` shape, replace Python `set(graph)` /
  `set(graph[u])` row arithmetic with a native lazy iterator that snapshots
  adjacency by node index and emits non-edge Python tuples one at a time.
- This avoids the previously rejected full `Vec<(u, v)>` pair materialization,
  but still preserves the `0..n` CPython `set.pop()` observable order used by
  the gauntlet fixture.

Gates and timing evidence:
- Candidate source passed:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`
  on RCH worker `vmi1153651`.
- Candidate release build passed:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  on RCH worker `vmi1264463`.
- Focused direct loop preloaded the built
  `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` as
  `franken_networkx._fnx`, with `PYTHONHASHSEED=0`,
  `OMP_NUM_THREADS=1`, and `OPENBLAS_NUM_THREADS=1`.
- Parity matched vendored NetworkX on the 900-node / p=0.008 / seed=9143
  gauntlet fixture: checksum `4.829200199316912e18` for both engines.

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `non_edges_sparse_undirected`, exact-int lazy iterator candidate | `95.512 ms` | `78.133 ms` | `0.818x` | loss |

Mean timing in the same 15-sample loop: FNX `94.927 ms`, NetworkX
`78.602 ms`, ratio `0.828x`.

Decision:
- Reject/no-ship. The source hunk was manually reverted after the native lazy
  iterator remained slower than NetworkX and slower than the current Python
  wrapper substrate on the focused direct loop.
- Candidate score: `0` wins / `1` loss / `0` neutral.

Do not repeat:
- Do not retry a PyO3 per-pair tuple-yielding `non_edges` iterator for
  exact-int simple graphs as a standalone lever. It removes full-pair
  materialization but loses the savings back at the per-yield Python boundary
  and adjacency snapshot setup.
- Next credible route should be consumer-fused: score default-ebunch link
  prediction or another downstream non-edge consumer without exposing every
  pair as a Python tuple.

## 2026-06-21 Cod-B Native MultiDiGraph Compose No-Ship (`br-r37-c1-04z53`, cod-b)

Scope: fresh BOLD-VERIFY pass after `bv --robot-triage` and `br ready`,
targeting the current String-keyed multigraph-attribute compose gap. Reused
the existing clean worktree `/data/projects/.worktrees/fnx-bt-3` and
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; no new
`.scratch` or perf-proof worktree was created.

Alien-graveyard / alien-artifact hypothesis:
- Apply the boundary-batching primitive: perform the H-wins keyed-edge compose
  merge directly over Rust multigraph storage instead of materializing both
  `edges(keys=True, data=True)` views into a Python `_edge_map`.
- Matched guidance: compact graph representation, batched boundary handoff,
  and cache-local sparse/graph traversal. The lever was deliberately radical
  enough to skip the public EdgeView materialization that dominated the prior
  `compose(MultiDiGraph)` and `compose(MultiGraph)` rows.

Baseline current-source direct head-to-head:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `compose_MultiGraph_string_attr`, 420 nodes / 18,900 result keyed edges | `383.614 ms` | `48.439 ms` | `0.126x` | loss |
| `compose_MultiDiGraph_string_attr`, 420 nodes / 18,900 result keyed edges | `125.134 ms` | `45.402 ms` | `0.363x` | loss |

Candidate attempts, both reverted:

| Candidate | FNX median | NetworkX median | Ratio vs NetworkX | Decision |
| --- | ---: | ---: | ---: | --- |
| exact `MultiDiGraph._native_compose` with Rust storage merge and eager Python-dict-to-`AttrMap` conversion | `108.573 ms` | `41.254 ms` | `0.380x` | reject |
| same native compose with Python edge mirrors authoritative and dirty-marked result attrs | `106.738 ms` | `39.730 ms` | `0.372x` | reject |

Validation:
- Candidate parity guard ran before timing: `fnx.compose` output matched
  `networkx.compose` for node attrs, graph attrs, sorted keyed edge attrs, and
  weighted attr checksum.
- Candidate compile gates passed:
  `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` on
  `vmi1153651` and `ovh-a`.
- Reverted-source release reinstall was run before final conformance checks.
- Focused compose/operator conformance on the reverted source:
  `tests/python/test_graph_operators_parity.py`,
  `tests/python/test_relabel_operator_no_double_build_parity.py`, and
  `tests/python/test_attribute_preservation_parity.py`: `32 passed`.
- Post-revert filtered RCH gauntlet rerun for the prior
  `non_edges_sparse_undirected` gap completed on `vmi1149989` with FNX
  `474.09 ms` and NetworkX `471.87 ms` (`0.995x`, neutral, overlapping
  intervals). This is evidence that `non_edges` is not the same clear loss on
  every worker/run, but it is not a domination win and does not rescue the
  rejected compose candidate.

Decision:
- Reject/no-ship. The native compose merge removed some Python edge-map work
  but the remaining public Python attribute-copy/key-display boundary still
  leaves `MultiDiGraph.compose` at roughly `0.37x` vs NetworkX.
- Candidate score: `0` wins / `1` loss / `0` neutral.
- Current active compose gaps remain `MultiDiGraph` and `MultiGraph`
  String-keyed attributed compose.

Do not repeat:
- Do not retry a standalone exact `MultiDiGraph._native_compose` that still
  returns a fully attributed Python graph by copying every edge attr dict.
- Do not spend another pass on the same `_edge_map`-avoidance family unless
  the lever changes the attribute substrate or fuses compose with a downstream
  consumer so the graph-result boundary is not paid eagerly.

## 2026-06-21 Cod-B Public Gauntlet + `non_edges` Set-Pop No-Ship (`br-r37-c1-04z53`, cod-b)

Scope: fresh BOLD-VERIFY pass after `bv --robot-triage` and `br ready`,
focused on current head-to-head gaps against vendored NetworkX. Reused
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; no new
worktree was created.

Baseline/current public-gauntlet evidence:
- Command family:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=.venv/bin:$PATH PYTHONPATH=crates/fnx-python/benches:python:legacy_networkx_code PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --bench public_api_gauntlet --features pyo3/abi3-py310 -- --noplot --sample-size 10 --warm-up-time 1 --measurement-time 2`
- RCH worker: `vmi1227854`.
- Current head-to-head score: `9` wins / `1` loss / `0` neutral vs
  NetworkX.

| Workload | FNX mean | NetworkX mean | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `flow_hierarchy_weighted_cyclic_dag` | `894.53 ms` | `1.3710 s` | `1.53x` | win |
| `within_inter_cluster_explicit_community` | `477.23 ms` | `875.40 ms` | `1.83x` | win |
| `non_edges_sparse_undirected` | `453.53 ms` | `419.38 ms` | `0.925x` | loss |
| `raw_adamic_adar_repeated_overlap` | `549.76 ms` | `1.6527 s` | `3.01x` | win |
| `raw_resource_allocation_repeated_overlap` | `499.15 ms` | `1.6117 s` | `3.23x` | win |
| `raw_preferential_attachment_repeated_overlap` | `432.40 ms` | `453.16 ms` | `1.05x` | win |
| `raw_cn_soundarajan_hopcroft_repeated_overlap` | `421.01 ms` | `1.6991 s` | `4.04x` | win |
| `raw_ra_index_soundarajan_hopcroft_repeated_overlap` | `587.12 ms` | `2.0254 s` | `3.45x` | win |
| `digraph_to_undirected_attr_heavy` | `4.4177 s` | `4.8616 s` | `1.10x` | win |
| `multidigraph_to_scipy_sparse_array_csr_int_weights` | `159.79 ms` | `243.98 ms` | `1.53x` | win |

Radical lever tested and reverted:
- Alien-graveyard / alien-artifact hypothesis: preserve exact CPython
  `set.pop()` iteration semantics in a PyO3 helper for simple `Graph`
  `non_edges`, avoiding public adjacency-row materialization while keeping
  NetworkX-observable pair order.
- Candidate source passed `rch exec -- cargo check -p fnx-python --benches
  --features pyo3/abi3-py310`.
- Candidate conformance passed
  `tests/python/test_non_edges_order_conformance_guard.py -q`: `42 passed`.
- Additional direct seed sweep matched NetworkX output for `60` randomized
  simple graphs; digest
  `bc3e06e826bd4aeaa95deb936958006fff3f81257cfe5def9bc938b9687ad020`.
- Focused RCH timing setup did not produce samples on `hz2`: first with an
  incorrect vendored NetworkX path, then with NumPy missing on that worker.
- Same-process local release timing rejected the candidate:
  FNX median `368.138 ms`, NetworkX median `292.090 ms`, ratio `0.793x`.

Decision:
- Reject/no-ship. The PyO3 set-pop helper was source-reverted after the
  measured candidate remained slower than NetworkX.
- Candidate score: `0` wins / `1` loss / `0` neutral.
- Current active gap from this pass: `non_edges_sparse_undirected`.

Do not repeat:
- Do not retry a materializing PyO3 `Vec<(u, v)>` exact-order helper for
  `non_edges`; it preserves order but moves too much pair materialization cost
  into the boundary.
- Next credible route needs a streaming or consumer-fused boundary: either
  score default-ebunch link-prediction consumers without first creating Python
  non-edge pairs, or expose an exact-order lazy generator that avoids building
  the full pair vector while still matching NetworkX `set.pop()` semantics.

## 2026-06-21 Cod-A Tree Submodule Remeasure + Edge-Boundary Gate (`br-r37-c1-dv0uf`, cod-a)

Scope: fresh BOLD-VERIFY pass after `bv --robot-triage` selected the unowned
P0 release gate `br-r37-c1-dv0uf`, while the umbrella no-gaps perf bead
remained owned by `cod-b` and the only explicit unowned perf recommendation was
blocked. No new perf source lever was shipped in this pass.

Conformance gate:
- The failing `fnx-algorithms` unit expectation for
  `edge_boundary_directed(..., nbunch2=...)` was stale. Vendored NetworkX
  includes `("b", "a")` for overlapping directed `S,T` because
  `edge_boundary` applies its symmetric overlap predicate after taking DiGraph
  out-edges from `nbunch1`.
- Public Python parity check with vendored NetworkX and `PYTHONHASHSEED=0`
  returned `[("a", "b"), ("b", "a"), ("b", "b"), ("b", "c")]` for both FNX
  and NetworkX.

Perf probe:
- Command:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a AGENT_NAME=CrimsonRiver PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/franken_networkx/crates/fnx-python/benches:/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code/networkx rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head tree_submodule -- --noplot --sample-size 10 --warm-up-time 1 --measurement-time 2`
- RCH worker: `hz2`; requested target dir was rewritten to the worker-scoped
  `/data/projects/franken_networkx/.rch-target-hz2-pool-4a7eb17ce3437e25aacd2701aa3351d7`.
- Focused workload: `franken_networkx.tree.minimum_spanning_tree` on the
  checked-in `networkx_head_to_head_tree_submodule` simple weighted
  `Graph`, n=1000/e=4999. The harness asserts parity before timing.

| Workload | FNX estimate | NetworkX estimate | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `fnx_tree.minimum_spanning_tree`, n=1000/e=4999 | `25.729 ms` | `9.9081 ms` | `0.385x` | loss |

Win/loss/neutral accounting for this pass: `0` wins / `1` loss / `0` neutral.

Alien-graveyard / alien-artifact routing:
- Failure signature: native algorithm work is not enough; the loss sits at the
  Python graph-result boundary and public submodule materialization path.
- Matched primitive family: compact CSR/GraphBLAS-style graph representations
  and zero-copy/batched boundary construction, per the graveyard scan's
  cache-local sparse-graph and boundary-minimization guidance.
- Rejected route: another top-level wrapper dispatch through
  `franken_networkx.minimum_spanning_tree`; current-source scorecard and this
  fresh row both show it fails after public graph materialization.
- Next retry predicate: only retry when the lever changes native result
  construction or graph boundary layout, e.g. emitting the tree graph directly
  from Rust with Python node/edge attribute mirrors populated in one pass, or a
  compact edge-stream handoff that avoids `_from_nx_graph` and repeated Python
  adjacency-row work.

Do not repeat:
- Do not claim a tree-submodule win from a pre-rebase or different-source row.
- Do not use cross-worker self-speedup as keep proof for this family.
- Do not ship a shallow wrapper reroute unless it beats vendored NetworkX on
  the public submodule API after graph materialization.

## 2026-06-21 Cod-B MultiDiGraph CSR Int-Data Bold-Verify (`br-r37-c1-04z53`, cod-b)

Scope: fresh re-authed cod-b verification of the sparse-boundary / CSR
handoff route for default-order integer-weighted
`MultiDiGraph.to_scipy_sparse_array(format="csr", dtype=None)`, under the
disk-low constraint to reuse
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b` and run
only a focused per-crate Criterion row.

Focused harness:
- Added/used `public_api_gauntlet`
  `multidigraph_to_scipy_sparse_array_csr_int_weights`, a deterministic
  2,000-node / 16,000-keyed-edge integer-weighted `MultiDiGraph` fixture.
- The harness asserts sparse parity before timing via shape and
  `(_FNX_MDG_MATRIX != _NX_MDG_MATRIX).nnz == 0`.

RCH evidence:

| Run | Worker | FNX mean | NetworkX mean | Ratio vs NetworkX | Verdict |
| --- | --- | ---: | ---: | ---: | --- |
| baseline/current-row before local typed-source probe | `vmi1227854` | `123.43 ms` | `235.16 ms` | `1.91x` | win |
| typed int-data probe rerun | `vmi1153651` | `326.29 ms` | `528.00 ms` | `1.62x` | win vs NetworkX, not same-worker self-proof |

Additional local parity smoke after the typed extension install:
integer-weight and float-weight `MultiDiGraph` sparse exports both matched
NetworkX and preserved dtype on the focused fixture.

Decision:
- The focused current-row ratio vs NetworkX is a win. Do not count the
  cross-worker after/before delta as proof for or against the typed int-data
  source lever.
- The cod-b local no-ship/revert was not kept once `main` moved to the
  committed typed route (`2655e8add`); do not undo current committed peer work
  from this session.

Do not repeat:
- Do not use cross-worker Criterion numbers as keep/revert proof for this
  exporter. Same-worker or same-process release timing is required for a
  self-speedup claim.
- Remaining sparse-export work should target dirty/live high-unique
  `MultiDiGraph` rows or a deeper SciPy/native CSR construction boundary, not
  another standalone row-streaming or dtype-scan microprobe.

## 2026-06-21 Tree Submodule Spanning-Tree Route Rejection (`br-r37-c1-04z53`, cod-b)

Scope: verify and close the disk-low code-only lever that routed
`franken_networkx.tree.minimum_spanning_tree` and
`franken_networkx.tree.maximum_spanning_tree` through the existing top-level fnx
implementations instead of calling
`networkx.algorithms.tree.*_spanning_tree` and converting through
`_from_nx_graph`.

Evidence:
- First attempted the exact requested spelling
  `rch exec -- cargo bench -p fnx-python --release --bench networkx_head_to_head
  tree_submodule -- --noplot --sample-size 10 --warm-up-time 1
  --measurement-time 2`, but this Cargo rejected `--release` for `bench`.
  No benchmark body ran in that failed invocation.
- The actual one crate-scoped benchmark was
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b
  rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head
  tree_submodule -- --noplot --sample-size 10 --warm-up-time 1
  --measurement-time 2` on `hz1`. RCH rewrote the target dir to a worker-scoped
  path.
- The added Criterion setup asserts the tree-submodule MST signature against
  vendored NetworkX before timing.

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `franken_networkx.tree.minimum_spanning_tree` simple weighted `Graph`, n=1000/e=4999 | `15.807 ms` | `13.331 ms` | `0.843x` | loss |

Decision:
- Reject/no-ship. The submodule route was reverted to the prior NetworkX
  delegate plus `_from_nx_graph` conversion, and the no-conversion regression
  test was removed.
- Keep the narrow `networkx_head_to_head_tree_submodule` bench row so future
  work can remeasure the public submodule boundary directly.
- Do not retry top-level fnx wrapper dispatch for simple-graph submodule MST as
  a standalone lever. A future route needs a faster native simple-graph result
  construction path or a larger algorithmic win that beats NetworkX after
  Python graph materialization.

## 2026-06-21 Cod-A Tree Submodule Diagnostic Bench, Superseded by Revert (`br-r37-c1-04z53.9157`, cod-a)

Scope: partial-resume measurement of the same tree-submodule route before
rebasing onto the cod-b rejection commit `1f4bc9171`. This records the actual
cod-a RCH result and setup failures, but it is not a current-source keep: after
the rebase, `python/franken_networkx/tree.py` again delegates submodule
MST/maxST through NetworkX plus `_from_nx_graph` conversion.

Evidence:
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-treebench-20260621T0156`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
  RCH rewrote it to a worker-scoped target on `hz1` for remote execution.
- Measured command:
  `AGENT_NAME=CrimsonRiver BR_AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- env PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH cargo bench -p fnx-python --bench tree_submodule_head_to_head`.
- The new Criterion bench asserts weighted sparse simple-graph MST/maxST
  parity before timing and uses vendored NetworkX
  `legacy_networkx_code/networkx` as the oracle.

Measured release timing on a 900-node / 3,599-edge weighted sparse simple
graph, four public API calls per Criterion iteration:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `franken_networkx.tree.minimum_spanning_tree` | `25.574 ms` | `39.899 ms` | `1.560x` | win |
| `franken_networkx.tree.maximum_spanning_tree` | `26.427 ms` | `46.737 ms` | `1.769x` | win |

Setup failures recorded:
- `cargo bench ... -- --sample-size 10 --warm-up-time 1 --measurement-time 2`
  built the bench profile but Criterion 0.8 rejected `--sample-size`; no
  samples were collected.
- The first registered target attempt was missing `harness = false` and ran as
  a zero-test harness; no Criterion samples were collected.
- The next setup attempts reached Python startup but failed before timing
  because the worker had no installed `_fnx` extension and then no optional
  `numpy` dependency. The checked-in bench now preloads the bench-built
  `lib_fnx.so` as `franken_networkx._fnx` and installs a fail-fast dummy
  `numpy` module so import-time drawing setup does not block this tree-only
  workload.

Conformance and gates:
- `rustfmt --check crates/fnx-python/benches/tree_submodule_head_to_head.rs`.
- `git diff --check`.
- `rch exec -- cargo check -p fnx-python --benches --features pyo3/abi3-py310`.
- `ubs $(git diff --name-only --cached)` after replacing the parity `!=`
  checks with `operator.eq` to avoid a scanner false positive; exit `0`.
- `python -m py_compile python/franken_networkx/tree.py
  tests/python/test_algorithms_tree_submodule.py`.
- Focused tree-submodule pytest with the bench-built release extension
  preloaded as `franken_networkx._fnx`: `21 passed` after rebasing onto the
  route-revert source.

Decision:
- Superseded/no-ship. The cod-a run produced `2` positive diagnostic ratios
  before the rebase, but the current branch includes the cod-b current-source
  loss and route revert above. Do not count these rows as active current-source
  wins.
- Remaining deeper work: separate fallback/multigraph tree rows if a future
  profile shows a live loss outside this simple-graph public route.

## 2026-06-21 Fresh Cod-A Current-Source Tree Submodule Verification (`br-r37-c1-04z53.9157`, cod-a)

Scope: re-authenticated cod-a restart on current `main` after rebasing onto the
cod-b tree-submodule route revert and the checked-in focused harness. This is
the live current-source decision for the `franken_networkx.tree`
minimum/maximum spanning-tree public submodule surface.

Evidence:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-a`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
  RCH rewrote it to worker-scoped target
  `/data/projects/franken_networkx/.rch-target-hz1-pool-411d55b5f6ed4833c6ebe01f30cd4b74`
  on `hz1`.
- Command:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --bench tree_submodule_head_to_head --features pyo3/abi3-py310 -- --noplot --sample-size 10 --warm-up-time 1 --measurement-time 2`.
- The harness asserts weighted sparse simple-graph MST/maxST parity against
  vendored NetworkX before timing and preloads the bench-built `_fnx` extension.
- Alien route considered: graphic-matroid/DSU work is already in the top-level
  fnx native kernels; the remaining candidate is boundary/materialization
  removal for the submodule wrapper. Current source still pays NetworkX
  delegate plus `_from_nx_graph`, and the direct top-level reroute is already
  rejected above.

Measured current-source release timing on a 900-node / 3,599-edge weighted
sparse simple graph, four public API calls per Criterion iteration:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `franken_networkx.tree.minimum_spanning_tree` | `230.97 ms` | `81.677 ms` | `0.354x` | loss |
| `franken_networkx.tree.maximum_spanning_tree` | `254.50 ms` | `97.596 ms` | `0.383x` | loss |

Decision:
- Reject/no-ship for current source. The submodule route remains slower than
  NetworkX after public graph materialization, so no runtime code was changed.
- Keep the focused bench harness as evidence machinery only.
- Do not retry the simple reroute family. A future attempt needs a deeper
  result-construction/materialization primitive that beats NetworkX after
  preserving graph/node/edge attributes, ordering, and exception behavior.

## 2026-06-21 MultiDiGraph Lazy Tarjan Strong-Connectivity Keep (`br-r37-c1-1pmou`, cod-a)

Scope: close the measured `MultiDiGraph.is_strongly_connected` negative-case
loss where the first node is a singleton SCC and the remaining graph is large.
The predecessor path built full successor and predecessor CSR adjacency and ran
two reachability passes, so it paid for every edge even though NetworkX's
boolean predicate stops after the first SCC emitted by Tarjan.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260621T0012`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- The requested shared target hit incompatible-rustc E0514 (`cc`,
  `target_lexicon`, and `serde` were compiled by a different nightly). No
  cleanup or deletion was performed; release proof runs used fresh target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-boldverify-20260621T0042`.
- RCH post-rebase validation used fresh target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f3f2fb025-postrebase`.
  After RCH artifact retrieval that target was no longer safe for local
  `maturin develop` under the older nightly, so the final installed-extension
  pytest proof used fresh local target
  `/data/projects/.rch-targets/franken_networkx-cod-a-a1e6e7037-local-f20a92`.
- Oracle: vendored NetworkX `3.7rc0.dev0`; Python `3.13.7`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.

Baseline release timing on the tiny-first-SCC fixture:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| 3,000 edges | `0.436805 ms` | `0.237889 ms` | `0.545x` | loss |
| 6,000 edges | `0.688320 ms` | `0.239062 ms` | `0.347x` | loss |
| 12,000 edges | `1.220224 ms` | `0.241757 ms` | `0.198x` | loss |
| 21,000 edges | `1.985319 ms` | `0.246786 ms` | `0.124x` | loss |

Kept lever:
- Replace full forward+reverse CSR materialization with a lazy iterative
  Tarjan boolean test over distinct successor rows. Multiplicity is irrelevant
  for strong connectivity, so the native path returns `false` as soon as the
  first closed SCC is smaller than `n` and returns `true` only when the first
  closed SCC spans the graph.

Final release timing:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| 3,000 edges | `0.097704 ms` | `0.391961 ms` | `4.012x` | win |
| 6,000 edges | `0.096753 ms` | `0.396670 ms` | `4.100x` | win |
| 12,000 edges | `0.099048 ms` | `0.403423 ms` | `4.073x` | win |
| 21,000 edges | `0.098226 ms` | `0.265812 ms` | `2.706x` | win |
| strongly connected control, 6,500 edges | `1.382393 ms` | `7.679361 ms` | `5.555x` | win |

Conformance and gates:
- Focused pytest:
  `tests/python/test_directed_multigraph_degenerate_parity.py` and
  `tests/python/test_strongly_connected_conformance.py` passed `397` after the
  final rebase.
- Randomized direct `MultiDiGraph.is_strongly_connected` oracle sweep passed
  `0` mismatches across `200` deterministic small multigraph cases.
- `cargo fmt --check`: pass.
- `python -m py_compile python/franken_networkx/__init__.py
  tests/python/test_directed_multigraph_degenerate_parity.py`: pass.
- `rch exec -- cargo check -p fnx-python --all-targets --features
  pyo3/abi3-py310`: pass.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features
  pyo3/abi3-py310 -- -D warnings`: pass.
- `rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`: pass
  (`27 passed`).
- `rch exec -- cargo build -p fnx-python --release --features
  pyo3/abi3-py310`: pass.
- `rch exec -- cargo bench -p fnx-python --features pyo3/abi3-py310
  --no-run`: pass.
- `git diff --check`: pass.
- `ubs` over touched files: exit `0`, `0` critical issues; existing
  monolithic `algorithms.rs` warning inventory remains outside this lever.

Decision:
- Keep. The targeted negative row flips from `0.124x`-`0.545x` losses to
  `2.706x`-`4.100x` wins while the strongly connected control remains a clear
  win vs NetworkX.
- Do not reintroduce full forward+reverse CSR for the boolean `MultiDiGraph`
  predicate. If exact SCC component emission needs work, keep it separate from
  this boolean fast path.

## 2026-06-21 Max-Weight Matching Public-Loss Stale Correction (`br-r37-c1-88yc4`, cod-a)

Scope: remeasure the previous public `max_weight_matching` loss against the
vendored NetworkX oracle and decide whether an exact NetworkX-order blossom
port/fork is still a release blocker. The previous raw native route remains
invalid for exact edge-set tie-break parity.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260621T0012`.
- Release extension installed from fresh target
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-boldverify-20260621T0042`
  after the requested shared target hit incompatible-rustc E0514. No cleanup or
  deletion was performed.
- Oracle: vendored NetworkX `3.7rc0.dev0`; Python `3.13.7`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.

Fresh same-process release timing on weighted `gnp(300, 0.05, seed=11)`:

| Route | FNX median | NetworkX median | Ratio vs NetworkX | Exact edge set | Verdict |
| --- | ---: | ---: | ---: | --- | --- |
| public `fnx.max_weight_matching` delegate | `429.726415 ms` | `467.559904 ms` | `1.088x` | yes | stale loss closed |
| NetworkX direct-on-FNX graph object | `439.729672 ms` | `467.559904 ms` | `1.063x` | yes | no-ship; slower than current public |
| raw `_fnx.max_weight_matching` | `7.510473 ms` | `467.559904 ms` | `62.254x` | no | invalid keep |

Additional matching probes:
- Direct NetworkX-on-FNX exactness sweep over `120` nodes x `20` seeds reported
  `0` mismatches, but it was still slower than the current public delegate on
  the measured `300`-node target.
- `min_edge_cover` and `min_weight_matching` remain separate matching surfaces:
  raw native `min_edge_cover` reached `44.88x` speed but exact edge-set parity
  mismatched on `40 / 40` seeds, while direct NetworkX-on-FNX was exact but
  slower than the current route. No source change was shipped.

Decision:
- Close the stale public `max_weight_matching` loss. The currently shipped
  public API is exact and `1.088x` vs vendored NetworkX on the bead fixture.
- Keep raw native matching out of the public route until tie-break parity is
  solved; `62x` raw speed is routing evidence only, not a keep.
- Do not spend release-blocker time on an exact blossom port for this public row
  unless a new vendored-oracle measurement again shows a real public loss.

## 2026-06-20 MultiDiGraph Indexed CSR Bytearray Boundary Keep (`br-r37-c1-q2w4t`, cod-a)

Scope: revisit the large default-order `MultiDiGraph.to_scipy_sparse_array`
residual after the row-streaming-only rejection. The kept route combines the
alien-graveyard sparse-boundary/CSR guidance with two concrete boundary
changes: Rust emits mutable bytearray-backed CSR buffers for NumPy
`frombuffer`, and `MultiDiGraph` exposes an indexed ordered-edge visitor so the
CSR helper avoids both `edges_ordered_borrowed()` materialization and a second
node-index `HashMap`.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260620T2025Z`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Oracle import pinned to this worktree's vendored NetworkX path:
  `legacy_networkx_code/networkx`; Python `3.13.7`, `PYTHONHASHSEED=0`,
  `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `taskset -c 4`.
- Release extension installs used the fresh non-destructive target leaf
  `/data/projects/.rch-targets/franken_networkx-cod-a/f20a-local` because the
  shared requested target contained incompatible-rustc artifacts during
  `maturin develop`. No cleanup or deletion was performed. Final per-crate RCH
  check/test/clippy/build used the requested target and worker-scoped remotes.

Negative subattempts:
- Immutable `bytes` buffers were rejected immediately: SciPy may canonicalize
  CSR arrays in place, and `numpy.frombuffer(bytes)` produced
  `ValueError: WRITEBACKIFCOPY base is read-only` during sparse payload checks.
  The fix was to return `PyByteArray` so NumPy sees writable buffers.
- Mutable bytearray handoff without indexed storage traversal was only a
  partial route. Pinned same-process n=2000 timing improved the old fallback
  from `9.0834035 ms` to `6.5314375 ms` (`1.391x` self-speedup) but still
  trailed NetworkX `6.201046 ms` (`0.949x`). Kept only after adding the indexed
  visitor.

Final pinned release timing on deterministic default-order fixtures:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| n=500, 3k-edge `to_scipy MultiDiGraph` | `0.355143 ms` | `1.217437 ms` | `3.428x` | win |
| n=1000, 6k-edge `to_scipy MultiDiGraph` | `0.740944 ms` | `2.475911 ms` | `3.342x` | win |
| n=2000, 12k-edge `to_scipy MultiDiGraph` | `1.729036 ms` | `5.001066 ms` | `2.892x` | win |

Same-process fallback comparison for the n=2000 target:
- New indexed bytearray path: `2.3780405 ms`.
- Old list-returning CSR fallback with the new helper disabled: `3.3666895 ms`.
- NetworkX: `5.228357 ms`.
- Result: new path is `1.416x` faster than the old fallback and `2.199x`
  faster than NetworkX on the direct old/new/NX A/B loop.

Conformance and gates:
- Sparse payload parity: `diff_nnz=0` on every final sweep row; sums matched
  (`12002.0`, `24002.0`, `48003.0`). Existing dtype behavior remains unchanged:
  FNX old/new infer `int64` for integral float payloads while NetworkX reports
  `float64` on this synthetic fixture; sparse values match exactly.
- Focused sparse exporter parity:
  `pytest tests/python/test_to_scipy_sparse_default_native_parity.py
  tests/python/test_to_scipy_sparse_native_weighted_parity.py -q`:
  `304 passed`.
- `cargo fmt --check`: pass.
- `rch exec -- cargo check -p fnx-classes -p fnx-python --features
  pyo3/abi3-py310`: pass.
- `rch exec -- cargo test -p fnx-classes -p fnx-python --features
  pyo3/abi3-py310`: pass (`fnx-classes` `68 passed, 2 ignored`; `_fnx`
  `27 passed`).
- `rch exec -- cargo clippy -p fnx-classes -p fnx-python --all-targets
  --features pyo3/abi3-py310 -- -D warnings`: pass.
- `rch exec -- cargo build --release -p fnx-python --features
  pyo3/abi3-py310`: pass.
- UBS completed with exit `0` on the changed Rust sources and the focused
  Python parity test file. The all-touched-file UBS run was stopped after the
  Python pass spent roughly nine minutes on the pre-existing 56k-line public
  wrapper file with no findings emitted; focused pytest and `py_compile` cover
  that wrapper path for this slice.

Decision:
- Keep. The final indexed bytearray CSR boundary turns the current pinned
  default-order `MultiDiGraph.to_scipy_sparse_array` sweep into `3` wins /
  `0` losses / `0` neutral vs NetworkX, including the prior 12k-edge residual.
- Do not retry immutable `bytes` buffers for SciPy CSR arrays. Keep buffer
  handoff mutable, and route future sparse work toward dirty/live attr sync or
  full native sparse-array construction rather than Python list boundaries.

## 2026-06-20 Native Tuple Lattice Generator Keep (`br-r37-c1-ap7at`, cod-b)

Scope: close the public default non-periodic tuple-key lattice generator losses
for `triangular_lattice_graph` and `hexagonal_lattice_graph`. The final keep
routes only the default `create_using=None`, `periodic=False`, nonnegative
integer shape path through native Rust construction; all periodic, custom
graph-factory, boolean-shape, and negative-shape cases remain on the existing
NetworkX-compatible Python fallback.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-b`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-20260620T204139Z`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Local release installs through the requested target hit incompatible-rustc
  E0514 from stale artifacts. No cleanup or deletion was performed. Local
  release installs used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-local-f20a92ec-lattice`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
- Direct timing command: pinned same-process release loop on core `4` with
  identical public FNX/NetworkX generator calls at shape `60x60`, parity digest
  asserted before timing.

Control and candidate rows:

| Workload | Old FNX fallback median | NetworkX median | Old ratio vs NetworkX | Candidate median | Candidate ratio vs NetworkX | Candidate vs old FNX | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `triangular_lattice_graph(60, 60)` | `14.366951 ms` | `5.038766 ms` | `0.351x` | `2.859337 ms` | `1.762x` | `5.025x` faster | keep |
| `hexagonal_lattice_graph(60, 60)` | `40.929678 ms` | `14.777368 ms` | `0.361x` | `11.023525 ms` | `1.341x` | `3.713x` faster | keep |
| `triangular_lattice_graph(60, 60, with_positions=False)` | `10.185578 ms` | `4.104106 ms` | `0.403x` | `2.063670 ms` | `1.989x` | `4.936x` faster | keep |
| `hexagonal_lattice_graph(60, 60, with_positions=False)` | `23.653816 ms` | `8.533418 ms` | `0.361x` | `6.158808 ms` | `1.386x` | `3.841x` faster | keep |

Rejected subattempt:
- Native edge construction with Python `set_node_attributes` position
  materialization was not enough for the default-position public rows:
  triangular default reached only `0.903x` vs NetworkX and hexagonal default
  reached only `0.698x`. The final keep moved tuple-key node labels and `pos`
  attributes into the native constructor result instead of looping in Python.

Supplemental RCH Criterion evidence:
- Command:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head lattice_generators -- --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`.
- Worker: `vmi1153651`; exit `0`.
- Criterion estimates: triangular FNX `15.017 ms` vs NetworkX `53.823 ms`
  (`3.584x`); hexagonal FNX `83.563 ms` vs NetworkX `100.74 ms` (`1.206x`).
  FNX rows had high outliers on the shared worker, so the pinned same-process
  loop above is the keep gate and Criterion is supplemental bench coverage.

Conformance and gates:
- Focused lattice conformance: `tests/python/test_lattice_generators.py -q`,
  `24 passed`.
- Per-crate RCH gates: `cargo check -p fnx-python --all-targets --features
  pyo3/abi3-py310`; `cargo clippy -p fnx-python --all-targets --features
  pyo3/abi3-py310 -- -D warnings`; `cargo test -p fnx-python --features
  pyo3/abi3-py310` (`27 passed`); `cargo build --release -p fnx-python
  --features pyo3/abi3-py310`.
- Local gates: `cargo fmt --check`; `git diff --check`.

Decision:
- Keep. Final focused score: `4` wins / `0` losses / `0` neutral vs NetworkX.
- Do not retry the Python `set_node_attributes` position loop for default
  lattice rows. If periodic lattice cases become an active loss, route them as
  a separate parity problem because NetworkX relabeling semantics differ.

## 2026-06-20 MultiDiGraph CSR Row-Streaming Boundary Reject (`br-r37-c1-04z53`, cod-a)

Scope: test the next large sparse multigraph residual route after the prior
dirty-key and default-order exporter probes. The candidate added a storage-level
`MultiDiGraph` row-streaming helper so the default-order CSR exporter could
avoid materializing `edges_ordered_borrowed()` and avoid rebuilding a node-index
hash map before summing parallel `(u, v)` buckets.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260620T2000`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- The requested target hit incompatible-rustc E0514 (`cc`, `target_lexicon`,
  and `serde` compiled by rustc `beae78130` while this checkout uses
  `f20a92ec0`). No cleanup or deletion was performed. Candidate/control release
  installs used fresh target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-boldverify-20260620T2001`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13.7`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.

Control source on deterministic default-order fixtures:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| n=500 `to_numpy MultiGraph` | `1.816 ms` | `2.398 ms` | `1.321x` | win |
| n=500 `to_scipy MultiGraph` | `1.868 ms` | `2.186 ms` | `1.170x` | win |
| n=2000 `to_numpy MultiGraph` | `21.265 ms` | `19.065 ms` | `0.897x` | loss |
| n=2000 `to_scipy MultiGraph` | `18.061 ms` | `15.779 ms` | `0.874x` | loss |
| n=500 `to_numpy MultiDiGraph` | `5.169 ms` | `5.372 ms` | `1.039x` | win |
| n=500 `to_scipy MultiDiGraph` | `4.687 ms` | `3.838 ms` | `0.819x` | loss |
| n=2000 `to_numpy MultiDiGraph` | `29.262 ms` | `34.027 ms` | `1.163x` | win |
| n=2000 `to_scipy MultiDiGraph` | `26.248 ms` | `21.473 ms` | `0.818x` | loss |

Candidate timing after release rebuild:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Candidate vs control | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| n=500 `to_scipy MultiDiGraph` | `4.408 ms` | `3.927 ms` | `0.891x` | `1.063x` faster | still loss |
| n=2000 `to_scipy MultiDiGraph` | `21.973 ms` | `17.132 ms` | `0.780x` | `1.195x` faster | still loss |
| n=500 native CSR helper | `4.163 ms` | n/a | n/a | `1.038x` faster | routing only |
| n=2000 native CSR helper | `21.330 ms` | n/a | n/a | `1.102x` faster | routing only |

Decision:
- Reject/no-ship. The storage streaming scan produced small-to-moderate FNX
  self-speedups, but it did not beat NetworkX on either public sparse exporter
  row; the n=2000 public ratio was still a clear `0.780x` loss.
- Source hunk manually reverted; `git diff` on
  `crates/fnx-classes/src/digraph.rs` and `crates/fnx-python/src/readwrite.rs`
  is empty.
- Candidate `rch exec -- cargo check -p fnx-python --features
  pyo3/abi3-py310` passed before rejection.
- Reverted-source release install passed from the fresh target. The focused
  artifact harness remained parity-green: `160` configs x `2` exporters,
  `0` fails, golden
  `bff9639b02900c23d43c585672cddf6a3e39676fa40c631efccec93bfeb44307`.

Do not repeat:
- Do not add a storage-level row-streaming CSR scan as a standalone lever for
  default-order `MultiDiGraph.to_scipy_sparse_array`; it trims native helper time
  but leaves the public row slower than NetworkX.
- Next route needs a real sparse boundary/layout change: direct NumPy/SciPy
  buffer handoff, cached CSR arrays with mutation guards, or an algorithmic
  bypass of SciPy construction cost for callers that immediately consume CSR.

## 2026-06-20 MultiDiGraph CSR Boundary Snapshot Reject (`br-r37-c1-04z53`, cod-b)

Scope: re-baseline the dirty/live large-sparse `MultiDiGraph` matrix-exporter
residual on a high-unique-pair fixture, then test two deeper CSR-boundary
variants without shipping either source hunk. The target is the default
`nodelist=None`, `dtype=None`, `format="csr"`, `weight="weight"` public sparse
export path after 388 public `G[u][v][k]["weight"] = ...` mutations.

Environment:
- Agent Mail identity and CLI actor: `CrimsonRiver`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-20260620T1956`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Per-crate RCH gates before editing passed:
  `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  and
  `rch exec -- cargo bench -p fnx-python --features pyo3/abi3-py310 --no-run`.
- Local release installs through the requested target hit incompatible-rustc
  E0514 from stale artifacts; no cleanup or deletion was performed. Candidate
  installs used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0-csrrow`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
- Fixture: deterministic random seed `1`, 2,000 integer nodes, 12,000 keyed
  edges, 388 public post-construction dirty weight mutations, canonical CSR
  digest `f50fd3dec9442adb9b48b2392cf3c63305b314eca3a1e3e3b99f28c63e3d9e36`,
  `11974` canonical nonzeros, dtype `float64`, data sum `110516.75`.
- cProfile before editing: 40 calls to
  `_fnx.adjacency_csr_multidigraph_default_order_live_finite_checked` consumed
  `0.563 s` cumulative, about `14 ms` per call; Python/SciPy construction was
  not the primary cost.

Control source on the reproduced dirty fixture:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty high-unique 12k-edge MDG | `14.974176 ms` | `12.004329 ms` | `0.802x` | loss |
| `adjacency_matrix`, dirty high-unique 12k-edge MDG | `14.922177 ms` | `11.647203 ms` | `0.781x` | loss |

Candidate 1: source-row stream + Rust dtype flag:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Candidate vs control | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty high-unique 12k-edge MDG | `15.520080 ms` | `12.520007 ms` | `0.807x` | `0.965x` self-regression by FNX median | loss |
| `adjacency_matrix`, dirty high-unique 12k-edge MDG | `13.147295 ms` | `11.581038 ms` | `0.881x` | `1.135x` faster | still loss |

Candidate 2: in-call precise dirty weight snapshot + candidate 1:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Candidate vs control | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty high-unique 12k-edge MDG | `15.587537 ms` | `12.611771 ms` | `0.809x` | `0.961x` self-regression by FNX median | loss |
| `adjacency_matrix`, dirty high-unique 12k-edge MDG | `15.118008 ms` | `12.087389 ms` | `0.800x` | `0.987x` self-regression by FNX median | loss |

Conformance and gates:
- Candidate 1:
  `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed;
  focused sparse parity reported `304 passed`.
- Candidate 2:
  `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed;
  focused sparse parity reported `304 passed`.
- Both candidate source hunks were manually reverted before commit.

Decision:
- Reject/no-ship. Candidate 1 improved only the sibling `adjacency_matrix`
  row and still lost to NetworkX; candidate 2 regressed the sibling row and
  still lost on both target rows.
- Score on the target dirty slice: `0` wins / `2` losses / `0` neutral.
- Source code is restored to the pre-probe implementation; only ledger,
  scorecard, and Beads status changes are kept.

Do not repeat:
- Do not retry source-row hashing removal or Python dtype-scan elimination as
  standalone CSR levers for dirty high-unique `MultiDiGraph` sparse export.
- Do not retry in-call precise dirty weight snapshot without a new design that
  avoids mutating/copying Rust attr maps and also eliminates the dominant
  per-edge live-dict overhead.
- Next route needs a true native sparse-array/CSR buffer boundary, a compact
  edge-weight mirror specialized for numeric weights, or a larger algorithmic
  escape from per-edge Python dict semantics.

## 2026-06-20 MultiDiGraph Precise Dirty-Key Sparse Reject (`br-r37-c1-04z53`, cod-b)

Scope: test a narrower dirty/live sparse-export lever than the prior
borrowed-index rejection. `MultiDiGraph` already tracks exact dirty edge keys
for `G[u][v][k]` accesses, but the default-order sparse helpers treated any
dirty flag as "all edges dirty" and read every weight through the live Python
edge-attr dict path. The candidate made those helpers read stored Rust attrs
for untouched edges and use live dicts only for keys in the precise dirty set.

Environment:
- Agent Mail identity and CLI actor: `CrimsonRiver`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-20260620T181919`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Per-crate RCH release build passed:
  `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`.
  RCH rewrote the remote target to a worker-scoped cache.
- Local release install through the requested target hit incompatible-rustc
  E0514 from stale artifacts; no cleanup or deletion was performed. Candidate
  and control installs used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0-precise`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13`, `PYTHONHASHSEED=0`,
  `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
- Fixture: deterministic 2,000-node / 12,000-edge `MultiDiGraph`, 388 public
  post-construction `G[u][v][k]["weight"] = ...` mutations, default nodelist,
  default `weight="weight"`, sparse payload digest
  `558129dd98de2c818c51c16c33e6ec18786afaec48f8d3eddab018c0a24b3cdc`.

Control source on the same fixture:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty 12k-edge MDG | `9.680769 ms` | `7.469069 ms` | `0.772x` | loss |
| `adjacency_matrix`, dirty 12k-edge MDG | `10.238225 ms` | `7.189950 ms` | `0.702x` | loss |

Candidate timing after release rebuild:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Candidate vs control | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty 12k-edge MDG | `7.275282 ms` | `6.754456 ms` | `0.928x` | `1.331x` faster | still loss |
| `adjacency_matrix`, dirty 12k-edge MDG | `11.222841 ms` | `7.623773 ms` | `0.679x` | `0.912x` regression | regression/loss |

Decision:
- Reject/no-ship. The candidate improved the direct sparse row but did not beat
  NetworkX, and it regressed the sibling `adjacency_matrix` row that routes
  through the same public sparse exporter.
- Source hunk reverted; final source has no code diff from the control route.
- Score on the target dirty slice: `0` wins / `2` losses / `0` neutral vs
  NetworkX; self-score `1` improvement / `1` regression.
- Candidate `rch exec -- cargo check -p fnx-python --features
  pyo3/abi3-py310` passed. Reverted-source gates passed: `cargo fmt --check`,
  `git diff --check`, focused sparse parity
  `304 passed` (`test_to_scipy_sparse_native_weighted_parity.py` plus
  `test_to_scipy_sparse_default_native_parity.py`).

Do not repeat:
- Do not use precise dirty-key stored-attr bypass as a standalone lever for the
  dirty `MultiDiGraph` sparse exporter. It moves one row closer to parity but
  still loses and regresses `adjacency_matrix`.
- Next route needs a true native sparse-array/CSR boundary or a design that
  removes the Python/SciPy handoff cost while preserving dtype inference and
  live attr semantics; do not spend another patch on per-edge live-dict lookup
  selection alone.

## 2026-06-20 MultiDiGraph Dirty Sparse Boundary Borrowed-Index Reject (`br-r37-c1-kqh2u`)

Scope: re-baseline the large sparse multigraph exporter residual and test one
dirty/live edge-attribute boundary lever. The clean default-order integer-index
fixture is already a win; the active loss reproduced only on the dirty
`MultiDiGraph` path with public edge-attribute mutations.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260620T184133Z`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- The exact requested target hit incompatible-rustc E0514 from older artifacts.
  No cleanup, deletion, or reset was performed. Release and benchmark proof used
  fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-kqh2u`.
- Oracle: NetworkX `3.6.1`, Python `3.13.7`, `PYTHONHASHSEED=0`,
  `taskset` core `4`.
- Alien route applied: cache/layout/Swiss-table guidance translated to a
  borrowed live-weight index attempt intended to avoid per-edge owned
  `(u, v, key)` tuple construction and hash lookup on the dirty exporter path.

Clean fixture sanity, not the target loss:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, clean default-order n=2000 | `1.390486 ms` | `3.557171 ms` | `2.558x` | win |
| `adjacency_matrix`, clean default-order n=2000 | `1.518057 ms` | `3.632664 ms` | `2.393x` | win |

Dirty/live baseline on the active residual fixture:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty 12k-edge MDG | `11.083094 ms` | `7.516955 ms` | `0.678x` | loss |
| `adjacency_matrix`, dirty 12k-edge MDG | `11.440620 ms` | `6.928440 ms` | `0.606x` | loss |

Rejected lever:
- Pre-index `edge_py_attrs` live weights by borrowed `(&str, &str, usize)`
  once inside the Rust helper, then stream CSR without per-edge string clones or
  owned lookup-tuple construction.

Candidate timing after release rebuild:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty 12k-edge MDG | `14.510345 ms` | `6.259952 ms` | `0.431x` | regression |
| `adjacency_matrix`, dirty 12k-edge MDG | `9.431321 ms` | `5.827642 ms` | `0.618x` | still loss |

Decision:
- Reject/no-ship. The source hunk was reverted because the target
  `to_scipy_sparse_array` row regressed from `0.678x` to `0.431x`, and the
  `adjacency_matrix` row remained a loss.
- Score on the target dirty slice: `0` wins / `2` losses / `0` neutral.
- Parity digest matched in the candidate probe.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed on
  the candidate; `cargo fmt --check` passed after revert. Final source has no
  code diff.
- Post-revert release reinstall from the fresh target confirmed the installed
  extension was back on the final source and still losing on the same dirty
  fixture shape with digest parity:
  `to_scipy_sparse_array` FNX `12.386839 ms` vs NetworkX `7.455365 ms`
  (`0.602x`), `adjacency_matrix` FNX `18.037455 ms` vs NetworkX `7.471376 ms`
  (`0.414x`), digest
  `c29d2099856ac22e34cb12781f7d70f407c40512ca621cfe74e071c843115c44`.
- Final gates on the reverted source: `cargo fmt --check`, `git diff --check`,
  `python -m py_compile python/franken_networkx/__init__.py`,
  focused sparse exporter parity `297 passed`,
  `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`,
  `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`,
  and
  `rch exec -- cargo bench -p fnx-python --features pyo3/abi3-py310 --no-run`
  all passed.

Do not repeat:
- Do not front-load all live weight dictionary lookups into a borrowed index for
  dirty `MultiDiGraph` sparse export as a standalone lever.
- Do not claim the clean default-order sparse wins as closure for dirty/live
  boundary losses.

Next route:
- Sync only dirty weight keys into inner attrs and clear the dirty state before
  CSR export, or bypass Python tuple/list construction with a true native sparse
  array boundary for dirty `MultiDiGraph` rows.

## 2026-06-20 Default-Order Matrix Export + Dijkstra Emitter No-Ships (`br-r37-c1-04z53`)

Scope: test two radical-but-narrow boundary levers from the current loss
frontier before touching broader graph semantics: default-order multigraph
matrix export without repeated nodelist lookup, and path-heavy Dijkstra Python
object emission without duplicate display-key lookups. Both routes were
measured, reverted, and left as routing evidence only.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=CrimsonRiver`
  / cod-b.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-20260620T181919`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Exact requested target dir hit incompatible-rustc E0514 from older artifacts
  during the matrix bench setup. No cleanup, deletion, or reset was performed.
  Release and benchmark proof used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0`.
- RCH needed absolute `PYTHONPATH` entries for the public-gauntlet Python
  module and vendored NetworkX. The worker image did not have SciPy, so the
  sparse exporter row failed with `ModuleNotFoundError: No module named
  'scipy'` and the dense `to_numpy_array` sibling became the measurable route.

Matrix exporter evidence:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Candidate vs FNX baseline | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| Baseline `MultiDiGraph.to_numpy_array(default weight)`, 2000 nodes, RCH Criterion on `vmi1167313` | `98.274 ms` | `136.28 ms` | `1.3867x` | baseline | current win |
| Default-order COO/nodelist bypass candidate, same worker | `102.83 ms` | `142.91 ms` | `1.3896x` | `0.956x` | reject |
| Dense f64 slab default-order candidate, same worker | `104.63 ms` | `141.14 ms` | `1.349x` | `0.939x` | reject |

Dijkstra emitter evidence:

Fixture: synthetic directed integer-weight graph with a chain plus random
directed edges, source `0`, seed `20260620`, vendored NetworkX
`3.7rc0.dev0`, source-tree extension built by release `maturin build`.
The candidate cached finalized display-key objects and streamed each path
through `PyList::new` instead of first building a Rust `Vec<PyObject>`.
Parity digests matched for every row.

| Workload | Baseline FNX p50 | Candidate FNX p50 | NetworkX p50 | Baseline ratio vs NetworkX | Candidate ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Directed Dijkstra combined distance+path, n=600 / e=2999 | `0.457727 ms` | `0.601329 ms` | baseline `1.084615 ms`; candidate `1.519348 ms` | `2.3696x` | `2.5267x` | reject; FNX self-regression |
| Directed Dijkstra combined distance+path, n=1400 / e=6999 | `1.152663 ms` | `1.531261 ms` | baseline `4.482733 ms`; candidate `4.954216 ms` | `3.8890x` | `3.2354x` | reject; FNX self-regression |
| Directed Dijkstra combined distance+path, n=2600 / e=12999 | `5.737650 ms` | `5.246430 ms` | baseline `9.946764 ms`; candidate `9.730325 ms` | `1.7336x` | `1.8547x` | reject; noisy already-winning synthetic row |

Supplemental routing evidence:
- The existing undirected Dijkstra artifact harness
  `tests/artifacts/perf/20260615T-dijkstra-pred-boldfalcon/dijkstra_family_pass.py`
  on n=1400 / extra=6400 also showed a current win:
  `single_source_dijkstra` FNX p50 `1.992756 ms` vs NetworkX `5.079183 ms`
  (`2.550x`), with digest parity. That does not close the historical
  `br-r37-c1-0opkc` directed path-heavy loss because it is a different
  fixture.

Conformance and gates:
- Matrix dense-slab candidate focused parity passed:
  `tests/python/test_to_scipy_sparse_default_native_parity.py` reported
  `9 passed` before the candidate was reverted.
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
  passed during the Dijkstra emitter candidate.
- Release `maturin build --release --features pyo3/abi3-py310` completed for
  both the candidate and reverted baseline extension used in the Dijkstra A/B.
- Current source after both experiments has no code diff from the pre-probe
  baseline.

Decision:
- Reject and fully revert both matrix-export candidates. The measurable dense
  default-order row was already faster than NetworkX, and both candidates
  slowed FNX versus its own baseline.
- Reject and fully revert the Dijkstra display-key/PyList emitter candidate.
  It regressed the smaller two rows and only improved the largest synthetic
  row by roughly `1.09x` on a fixture that already beat NetworkX.
- Score impact for current release rows: `0` new wins / `0` new active losses /
  `0` neutral. This is negative evidence, not a kept performance entry.

Do not repeat:
- Do not retry default-order multigraph COO/nodelist bypass or dense f64 slab
  export for `to_numpy_array` unless a fresh fixture shows an active
  NetworkX-relative loss on that exact dense path.
- Do not retry the Dijkstra display-key cache / `PyList::new` streaming lever
  alone. Recover or port the exact `br-r37-c1-0opkc` directed residual fixture
  into a per-crate head-to-head bench first; only attack path emission there if
  the current baseline still loses.

## 2026-06-20 Node Expansion Raw-Kernel Public Route + Node-Degree XY Rebaseline (`br-r37-c1-04z53`)

Scope: target the active simple-undirected `node_expansion(G, S)` loss on the
BA2500/S1250 and WS2500/S625 cut-metric rows, then recheck the stale
`node_degree_xy` public-loss rows before spending another lever there.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-b`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-20260620T1318`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Exact requested target dir hit incompatible-rustc E0514 from older artifacts.
  No cleanup, deletion, or reset was performed. Release and benchmark proof used
  fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0-1318`.
- Alien route applied: cache-local bitmap/set-union guidance translated to a
  single PyO3 validate+compute primitive. The public wrapper now dispatches
  simple undirected `node_expansion` into the existing Rust indexed-neighbor
  union kernel; the Rust binding validates every node and raises NetworkX's
  missing-node error before the bitmap pass.

Baseline before this lever:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `node_expansion`, BA2500/S1250, RCH Criterion baseline on `vmi1149989` | `1.7826 ms` | `629.01 us` | `0.353x` | loss |
| `node_expansion`, WS2500/S625, RCH Criterion baseline on `vmi1149989` | `776.82 us` | `380.16 us` | `0.489x` | loss |

Kept lever:
- Import `_fnx.node_expansion` as `_raw_node_expansion` and route the public
  function to it for simple undirected nonempty sized `S`.
- Move missing-node validation into the Rust binding so the hot path does not
  pay a Python `all(node in G for node in S)` scan; missing nodes still raise
  `NetworkXError("The node X is not in the graph.")`.

Final accepted release timing:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `node_expansion`, BA2500/S1250, RCH Criterion on `vmi1152480` | `213.68 us` | `527.47 us` | `2.469x` | win |
| `node_expansion`, WS2500/S625, RCH Criterion on `vmi1152480` | `94.674 us` | `292.24 us` | `3.087x` | win |
| Local release sanity, BA2500/S1250 | `196.962 us` | `298.657 us` | `1.516x` | win |
| Local release sanity, WS2500/S625 | `73.424 us` | `137.229 us` | `1.869x` | win |

Fresh `node_degree_xy` rebaseline:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| public `fnx.node_degree_xy`, h512/s32, RCH Criterion on `vmi1153651` | `116.87 ms` | `336.80 ms` | `2.882x` | stale loss closed |
| public directed `fnx.node_degree_xy`, l512/f32, RCH Criterion on `vmi1153651` | `158.65 ms` | `336.86 ms` | `2.123x` | stale loss closed |
| raw `_fnx.node_degree_xy_rust`, h512/s32, RCH Criterion on `vmi1153651` | `29.948 ms` | `362.97 ms` | `12.120x` | valid win |
| raw directed `_fnx.node_degree_xy_rust`, l512/f32, RCH Criterion on `vmi1153651` | `38.594 ms` | `443.04 ms` | `11.479x` | valid win |

Conformance and gates:
- Release `maturin develop --release --features pyo3/abi3-py310` passed with
  the fresh target dir above.
- Focused graph-metrics expansion tests passed: `55 passed`.
- Focused graph-metrics expansion + conformance tests passed: `199 passed`.
- `cargo fmt --check` passed.
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
  passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  passed.
- `rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310` reported
  `27 passed`.
- `ubs --only=rust crates/fnx-python/src/algorithms.rs` completed with exit
  `0` (`0` critical issues; existing broad warning inventory remained).
- `ubs --only=python tests/python/test_graph_metrics_expansion.py` completed
  with exit `0` (`0` critical, `0` warning issues).
- `ubs --only=python python/franken_networkx/__init__.py tests/python/test_graph_metrics_expansion.py`
  timed out after `300s` in the large public module; Python syntax was still
  checked with `py_compile`, and focused pytest/bench parity gates are green.
- The head-to-head Criterion benches assert `node_expansion` and
  `node_degree_xy` result parity before timing.

Decision:
- Keep the `node_expansion` public raw-kernel route. The active rows flip from
  measured losses (`0.353x`, `0.489x`) to measured wins (`2.469x`, `3.087x`).
- Treat the old `node_degree_xy` public-loss rows as stale. The current public
  path wins on the same RCH head-to-head harness, and the raw path is now
  parity-checked by the bench before timing.
- Focused score for this pass: `4` public wins / `0` active losses / `0`
  neutral; raw side evidence adds `2` valid wins.

Do not repeat:
- Do not reintroduce a Python membership pre-scan before `node_expansion`; it
  measured as the dominant remaining overhead and kept BA below NetworkX.
- Do not spend another `node_degree_xy` lever until a fresh head-to-head row
  shows a current loss. The prior public-loss scorecard rows are stale.

## 2026-06-20 MultiGraph BFS Direct Borrowed Row Route (`br-r37-c1-1jm15`)

Scope: close the remaining dense-parallel `MultiGraph`
`bfs_edges(source=0)` loss split from `br-r37-c1-ij951`, preserving
NetworkX discovery order and Python-visible node display objects.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-bfs-20260620T1133Z`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Exact release install against the requested shared target dir hit
  incompatible-rustc E0514 because older target artifacts were present. No
  cleanup, deletion, or target reset was performed. Release proof used fresh
  non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-bfs-f20a92ec0`.
- Alien route applied: GraphBLAS/CSR frontier guidance and cache-local row
  traversal translated to a narrower primitive: avoid per-call full
  `Vec<Vec<usize>>` adjacency indexing and endpoint `String` clones for
  row-local `MultiGraph` BFS.

Baseline before this lever:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `bfs_edges(source=0)`, 1000-node / 5000-edge `MultiGraph`, same-process release loop | `0.684275 ms` | `0.499728 ms` | `0.730x` | loss |
| Prior `ij951` pinned sweep for the same residual | `0.796 ms` | `0.657 ms` | `0.825x` | loss |

Kept lever:
- Add a borrowed `MultiGraph::neighbors_iter` row iterator and route
  undirected `MultiGraph` `bfs_edges` through direct borrowed distinct-neighbor
  traversal. The PyO3 boundary keeps the discovered parent display object and
  emits the child row-display object, matching NetworkX's visible tuple order
  without rebuilding a full indexed adjacency map.

Final accepted release timing:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| Same-process release loop after borrowed helper | `0.489809 ms` | `0.530343 ms` | `1.083x` | win |
| Same-process release loop after `neighbors_iter` | `0.472939 ms` | `0.519132 ms` | `1.098x` | win |
| RCH Criterion `bfs_edges_mg1000_e5000` on `ovh-a` | `441.08 us` | `548.47 us` | `1.243x` | win |

Neutral/noisy evidence:
- An earlier RCH Criterion row on a different worker after only the borrowed
  helper was positive but marginal: FNX median `666.71 us` vs NetworkX
  `672.28 us` (`1.008x`). It was treated as routing evidence, not the final
  keep gate; the final `neighbors_iter` row above is the accepted benchmark.

Conformance and gates:
- `cargo fmt --check` passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  passed.
- `rch exec -- cargo test -p fnx-classes` reported `68 passed, 2 ignored`.
- Release `maturin develop --release --features pyo3/abi3-py310` passed with
  the fresh target dir above.
- Focused traversal conformance reported `204 passed`, then broader
  BFS/traversal parity reported `136 passed`.
- A too-broad `test_dicsr_cache_parity.py` run exposed unrelated directed
  multi-source Dijkstra finalize-order drift; follow-up bead
  `br-r37-c1-syrw5` records that work.

Decision:
- Keep. This converts the active `MultiGraph bfs_edges(source=0)` residual from
  a measured loss (`0.730x` in this clean worktree, `0.825x` in the earlier
  pinned sweep) to a measured win (`1.098x` same-process, `1.243x` Criterion).
- Final bead score: `1` win / `0` losses / `0` neutral vs NetworkX.

Do not repeat:
- Do not rebuild full indexed adjacency and `String` endpoint vectors for
  undirected `MultiGraph` BFS. Row-local borrowed traversal is the measured
  primitive for this surface.
- Do not treat the unrelated Dijkstra finalize-order failure as BFS evidence;
  it is tracked separately by `br-r37-c1-syrw5`.

## 2026-06-20 MultiDiGraph Weighted Sparse Export Live-Dict Slice (`br-r37-c1-wvuf7`)

Scope: target the measured weighted sparse/matrix exporter loss where
`_sync_rust_edge_attrs(..., edge_only=True)` dominated `MultiDiGraph`
`to_scipy_sparse_array` / `adjacency_matrix` at scale. The kept lever is a
native live-dict weight reader for `MultiDiGraph` dtype-`None` multigraph
exporters: walk the existing inner edge order, read live Python edge-attr
mirrors for the requested weight, fall back to Rust attrs only when no mirror is
present, and return to the exact Python fallback for present nonnumeric or
nonfinite weights.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-b`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-wvuf7-20260620T1045Z`.
- Requested target dir: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Exact requested local `maturin develop --release --features pyo3/abi3-py310`
  against the shared target dir failed with incompatible-rustc E0514. No
  cleanup or file deletion was performed.
- Release extension install used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-maturin-f20a`.
- Per-crate RCH gates completed for `fnx-python`: `cargo check -p fnx-python
  --benches`, `cargo clippy -p fnx-python --all-targets -- -D warnings`, and
  `cargo build -p fnx-python --release`.
- Head-to-head harness: same-process Python release timing against vendored
  NetworkX `3.7rc0.dev0`, `PYTHONHASHSEED=0`, public weighted graph
  construction with parity checked before timing for every row.

Baseline before this lever:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `MultiGraph n=250 to_scipy_sparse_array` | `0.699 ms` | `0.878 ms` | `1.256x` | win |
| `MultiGraph n=250 adjacency_matrix` | `0.734 ms` | `0.863 ms` | `1.176x` | win |
| `MultiGraph n=1000 to_scipy_sparse_array` | `3.299 ms` | `3.396 ms` | `1.029x` | win |
| `MultiGraph n=1000 adjacency_matrix` | `4.101 ms` | `3.658 ms` | `0.892x` | loss |
| `MultiGraph n=2000 to_scipy_sparse_array` | `14.671 ms` | `10.535 ms` | `0.718x` | loss |
| `MultiGraph n=2000 adjacency_matrix` | `13.482 ms` | `11.038 ms` | `0.819x` | loss |
| `MultiDiGraph n=250 to_scipy_sparse_array` | `0.856 ms` | `0.623 ms` | `0.728x` | loss |
| `MultiDiGraph n=250 adjacency_matrix` | `0.596 ms` | `0.594 ms` | `0.996x` | neutral |
| `MultiDiGraph n=1000 to_scipy_sparse_array` | `5.454 ms` | `2.513 ms` | `0.461x` | loss |
| `MultiDiGraph n=1000 adjacency_matrix` | `8.244 ms` | `2.681 ms` | `0.325x` | loss |
| `MultiDiGraph n=2000 to_scipy_sparse_array` | `17.289 ms` | `5.295 ms` | `0.306x` | loss |
| `MultiDiGraph n=2000 adjacency_matrix` | `14.045 ms` | `6.491 ms` | `0.462x` | loss |

Rejected subattempt:
- Routing the live-dict helper for both `MultiGraph` and `MultiDiGraph`
  improved directed rows but regressed undirected multigraph rows. Measured
  post-attempt ratios included `MultiGraph n=250 adjacency_matrix` `0.750x`,
  `MultiGraph n=1000 to_scipy_sparse_array` `0.663x`,
  `MultiGraph n=2000 to_scipy_sparse_array` `0.638x`, and
  `MultiGraph n=2000 adjacency_matrix` `0.608x`. That route was narrowed before
  commit; `MultiGraph` stays on the existing checked native sync path.

Final accepted release timing after narrowing the route to `MultiDiGraph`:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `MultiGraph n=250 to_scipy_sparse_array` | `0.637 ms` | `0.779 ms` | `1.224x` | win |
| `MultiGraph n=250 adjacency_matrix` | `0.684 ms` | `0.800 ms` | `1.170x` | win |
| `MultiGraph n=1000 to_scipy_sparse_array` | `2.576 ms` | `3.114 ms` | `1.209x` | win |
| `MultiGraph n=1000 adjacency_matrix` | `3.283 ms` | `3.835 ms` | `1.168x` | win |
| `MultiGraph n=2000 to_scipy_sparse_array` | `7.559 ms` | `8.444 ms` | `1.117x` | win |
| `MultiGraph n=2000 adjacency_matrix` | `7.823 ms` | `6.312 ms` | `0.807x` | loss |
| `MultiDiGraph n=250 to_scipy_sparse_array` | `0.489 ms` | `0.545 ms` | `1.113x` | win |
| `MultiDiGraph n=250 adjacency_matrix` | `0.494 ms` | `0.553 ms` | `1.119x` | win |
| `MultiDiGraph n=1000 to_scipy_sparse_array` | `1.946 ms` | `2.190 ms` | `1.125x` | win |
| `MultiDiGraph n=1000 adjacency_matrix` | `2.013 ms` | `2.724 ms` | `1.353x` | win |
| `MultiDiGraph n=2000 to_scipy_sparse_array` | `8.707 ms` | `6.324 ms` | `0.726x` | loss |
| `MultiDiGraph n=2000 adjacency_matrix` | `11.363 ms` | `8.008 ms` | `0.705x` | loss |

Focused repeat on the largest directed workload:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `MultiDiGraph n=2000 to_scipy_sparse_array` | `7.838 ms` | `5.392 ms` | `0.688x` | loss |
| `MultiDiGraph n=2000 adjacency_matrix` | `9.171 ms` | `5.652 ms` | `0.616x` | loss |

Self-speedups on targeted `MultiDiGraph n=2000` rows:
- `to_scipy_sparse_array`: `17.289 ms -> 8.707 ms`, `1.985x` in the expanded
  sweep; focused repeat `7.838 ms` gives `2.206x` vs baseline.
- `adjacency_matrix`: `14.045 ms -> 11.363 ms`, `1.236x` in the expanded
  sweep; focused repeat `9.171 ms` gives `1.531x` vs baseline.

Conformance and gates:
- `cargo fmt --check` passed.
- `rch exec -- cargo check -p fnx-python --benches` passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`
  passed.
- `rch exec -- cargo build -p fnx-python --release` passed after retrying
  remotely; an earlier local fallback against the shared target dir hit E0514.
- `maturin develop --release --features pyo3/abi3-py310` passed with the fresh
  target dir noted above.
- Focused sparse-export parity reported `297 passed`.
- Sparse plus numpy weighted exporter parity reported `305 passed`.

Decision:
- Keep the `MultiDiGraph` live-dict route as a measured partial: expanded final
  slice score `9` wins / `3` losses / `0` neutral vs NetworkX, and the target
  directed `n=2000` rows roughly halved their FNX runtime.
- Do not close the bead as fully dominated. The largest directed rows remain
  losses (`0.688x` and `0.616x` on focused repeat), so the next route must
  attack index construction and SciPy/NumPy boundary cost rather than edge-attr
  sync alone.

Do not repeat:
- Do not route `MultiGraph` through the live-dict helper without a different
  undirected COO strategy; the all-multigraph attempt regressed measured rows.
- Do not retry Python edges-view COO construction; prior evidence on this bead
  showed parity but net regression at small/medium sizes.
- Do not claim the scale row as solved from self-speedup. The largest
  `MultiDiGraph` exporter rows still lose to NetworkX.

Next route:
- Specialize default-order integer-index `MultiDiGraph` COO emission to avoid
  Python nodelist canonicalization, Python list handoff, and avoidable
  sparse-matrix construction overhead for the common `nodelist=None`,
  integer-node path.

## 2026-06-20 MultiDiGraph DAG Closeout (`br-r37-c1-11m92`)

Scope: re-baseline the claimed `MultiDiGraph` DAG losses on current `origin/main`
before trying another conversion-tax rewrite, then keep only measured wins. The
current source had already made `topological_sort`, `dag_longest_path`, and SCC
counting stale wins; the real remaining losses were `transitive_closure` and
`dag_longest_path_length`.

Environment:
- Agent: `CrimsonRiver` / `cod-a`.
- Worktree: `/data/projects/franken_networkx-cod-a-land`.
- Requested target dir for RCH gates:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Exact requested local `maturin develop --release --features pyo3/abi3-py310`
  install hit incompatible-rustc E0514 in that shared target dir; no cleanup or
  file deletion was performed.
- Release install used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-local-f20a92ec0`.
- Per-crate RCH build/check/clippy/test gates completed for `fnx-python`.
- Per-crate RCH bench gate completed on `vmi1149989`:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head multidigraph_connectivity_head_to_head -- --noplot`.
  The retrieved transcript reported exit `0` but did not include Criterion
  timing rows for this DAG surface, so the ratio evidence below comes from the
  same-process release harness.
- Head-to-head harness: same-process Python release timing against NetworkX
  `3.6.1`, `PYTHONHASHSEED=0`, identical 420-node / 1329-edge deterministic
  `MultiDiGraph` DAG with parallel keyed arcs and digest parity for every row.

Baseline before this lever:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `topological_sort` | `0.255564 ms` | `1.488430 ms` | `5.824x` | stale win |
| `dag_longest_path` | `1.446391 ms` | `2.216259 ms` | `1.532x` | stale win |
| `dag_longest_path_length` | `4.409575 ms` | `3.083493 ms` | `0.699x` | loss |
| `transitive_closure` | `1164.244211 ms` | `660.420907 ms` | `0.567x` | loss |
| `number_strongly_connected_components` | `0.125618 ms` | `0.426938 ms` | `3.399x` | stale win |

Kept levers:
- `transitive_closure` now uses a native `MultiDiGraph` distinct-successor CSR
  reachability pass for `reflexive=False`, then bulk-inserts missing keyed
  closure edges while preserving NetworkX node/edge/attr/order snapshots. Cases
  with row-key override mirrors fall back to the existing NetworkX-compatible
  path.
- `dag_longest_path_length` now computes the length directly from the
  predecessor dynamic program for directed multigraphs, avoiding a full
  `dag_longest_path` list allocation followed by Python multiedge re-indexing.

Final release timing:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Digest | Verdict |
| --- | ---: | ---: | ---: | --- | --- |
| `topological_sort` | `0.197824 ms` | `1.052203 ms` | `5.319x` | `a3fe6d8438cc328f` | win |
| `dag_longest_path` | `1.330331 ms` | `2.036158 ms` | `1.531x` | `a3fe6d8438cc328f` | win |
| `dag_longest_path_length` | `1.303539 ms` | `2.718360 ms` | `2.085x` | `cef5838d118dccd9` | win |
| `transitive_closure` | `265.605101 ms` | `627.405576 ms` | `2.362x` | `1c46fd2646166806` | win |
| `number_strongly_connected_components` | `0.116190 ms` | `0.356205 ms` | `3.066x` | `db55da3fc3098e9c` | win |

Self-speedups:
- `transitive_closure`: `1164.244211 ms -> 265.605101 ms`, `4.383x`.
- `dag_longest_path_length`: `4.409575 ms -> 1.303539 ms`, `3.383x`.

Conformance and gates:
- `pytest tests/python/test_transitive_closure_attrs.py tests/python/test_dag_additional.py -q`
  reported `35 passed`.
- `pytest tests/python/test_parity_conformance.py tests/python/test_transitive_closure_attrs.py tests/python/test_dag_additional.py -q`
  reported `230 passed`.
- `cargo fmt --check` passed.
- `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  passed.
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
  passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  passed.
- `rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310` reported
  `27 passed`.

Decision:
- Keep both levers. The measured DAG surface is now `5` wins / `0` losses /
  `0` neutral vs NetworkX, and both true baseline losses flipped to wins.

Do not repeat:
- Do not route `MultiDiGraph` transitive closure through Python edge-by-edge
  graph copies when `reflexive=False` and keyed-row mirrors are ordinary.
- Do not compute `dag_longest_path_length` by first materializing the full
  longest-path node list for directed multigraphs.
- Do not spend more time on the stale topological-sort, longest-path, or SCC
  count notes until a fresh same-process head-to-head row shows a real loss.

Next route:
- Move to remaining measured losses such as multigraph matrix exporters,
  path-heavy Dijkstra rows, or MultiGraph biconnected/MST surfaces; this DAG
  conversion-tax bead is closed.

## 2026-06-20 MultiGraph Keyed MST Native Route (`br-r37-c1-ij951`)

Scope: close the residual MultiGraph `minimum_spanning_tree` loss left by the
earlier biconnected-family route, preserving the NetworkX-observable
`MultiGraph` result type, selected parallel edge keys, graph/node/edge attrs,
and stable Kruskal tie order.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-a`.
- Worktree: `/data/projects/franken_networkx`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Local release install against the requested shared target failed with
  incompatible-rustc E0514 (`beae78130` artifacts vs current `f20a92ec0`).
  No cleanup or file deletion was performed. The local release extension was
  installed with fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-mst`.
- Exact-target RCH release build passed:
  `rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  on `vmi1149989`.
- Exact-target RCH bench attempt first fell back locally because no workers were
  admissible and hit the same shared-target E0514. The measured Criterion bench
  used the fresh non-destructive target dir:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head multigraph_biconnected -- --sample-size 10 --measurement-time 2`.
- Direct same-process Python sweeps pinned
  `PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx`
  after an unpinned probe resolved the editable package to a sibling scratch
  worktree; only pinned-current-checkout timings are used below.

Baseline before this lever:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `minimum_spanning_tree` old parity route on 1000-node / 5000-edge `MultiGraph` | `32.322 ms` | `10.103 ms` | `0.313x` | loss |
| `minimum_spanning_tree` old parity route on keyed custom fixture | `40.035 ms` | `12.915 ms` | `0.323x` | loss |

Kept lever:
- Add a PyO3 `multigraph_minimum_spanning_tree` helper that scans the
  `MultiGraph` edge snapshots directly, rejects nonnumeric/nonfinite or
  row-display-override cases back to the existing parity path, runs stable
  Kruskal with a compact union-find, and builds a new keyed `PyMultiGraph`
  result without a full fnx-to-NetworkX conversion.
- The public wrapper syncs edge attrs first, then accepts the native result only
  when the helper returns a `MultiGraph`; unsupported cases keep the previous
  NetworkX parity behavior.

Final same-process release sweep on the bead fixture (1000 nodes, 5000 edges,
seed `20260620`, NetworkX `3.6.1`, parity matched every row):

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `is_biconnected` | `0.358 ms` | `2.432 ms` | `6.801x` | win |
| `articulation_points` | `0.358 ms` | `1.743 ms` | `4.868x` | win |
| `biconnected_components` | `0.869 ms` | `2.468 ms` | `2.839x` | win |
| `minimum_spanning_tree` native | `8.040 ms` | `9.039 ms` | `1.124x` | win |
| `minimum_spanning_tree` old parity route | `32.322 ms` | `10.103 ms` | `0.313x` | rejected baseline |
| `bfs_edges(source=0)` | `0.796 ms` | `0.657 ms` | `0.825x` | loss |

Additional evidence:
- Custom keyed/attr-heavy `MultiGraph` fixture, same process:
  `minimum_spanning_tree` moved from `0.323x` old parity to `2.035x` native
  (`8.070 ms` FNX vs `16.426 ms` NetworkX), with exact digest parity.
- Criterion `networkx_head_to_head_multigraph_biconnected` final rows:
  `is_biconnected` `10.454x`, `articulation_points` `6.401x`,
  `biconnected_components` `4.065x`, and `minimum_spanning_tree` `1.214x`
  on the bench fixture.

Conformance and gates:
- `pytest tests/python/test_mst_node_label_parity.py -q` reported `55 passed`.
- `pytest tests/python/test_tree_bipartite.py -q` reported `63 passed`.
- `pytest tests/python/test_parity_conformance.py -q` reported `195 passed`.
- `cargo fmt --check` passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed.
- `rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  passed with the exact requested target dir through RCH remote execution.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  passed.
- `rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310` reported
  `27 passed`.

Decision:
- Keep. The MST residual flips from a measured `0.313x` loss to a `1.124x`
  win on the bead fixture and `1.214x` in Criterion.
- Current `ij951` surface accounting at this point was `4` measured wins
  (`is_biconnected`, `articulation_points`, `biconnected_components`,
  `minimum_spanning_tree`) / `1` measured loss (`bfs_edges`) / `0` neutral in
  the pinned same-process sweep. The `bfs_edges` residual was split and later
  closed by `br-r37-c1-1jm15`.

Do not repeat:
- Do not route ordinary numeric MultiGraph MST through `_networkx_graph_for_parity`;
  that old route remains a `0.313x` loss on the bead fixture.
- Do not collapse keyed MultiGraph MST to a simple `Graph`; the result must
  preserve `MultiGraph` type, selected edge keys, and attrs.
- Do not treat this MST section as the final `ij951` state; it is historical
  evidence before the separate `br-r37-c1-1jm15` BFS closeout.

Next route:
- See `br-r37-c1-1jm15` above for the subsequent MultiGraph
  `bfs_edges(source=0)` closeout. The MST residual is closed here.

## 2026-06-20 MultiGraph Biconnected Family Native Route (`br-r37-c1-ij951`)

Scope: target the open MultiGraph biconnected/MST loss cluster on current
`origin/main` from a clean detached worktree. The kept lever is a direct
ordered-adjacency MultiGraph biconnected-family route for vertex/edge-stack
queries; keyed MST construction is intentionally untouched and remains a loss.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-b`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-ij951-boldverify-20260620T061230Z`.
- Requested target dir: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Local `maturin develop` against the exact requested target dir failed with
  incompatible-rustc E0514 (`beae78130` artifacts vs current `f20a92ec0`).
  No cleanup or file deletion was performed. Release installs used fresh
  non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0`.
- Per-crate RCH bench:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head multigraph_biconnected -- --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`
  on `hz1`.
- Per-crate RCH release build:
  `rch exec -- cargo build -p fnx-python --release` on `vmi1153651`.
- Clippy gate:
  `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`
  completed green after rch remote sync timed out and fell back locally.
- Focused conformance:
  `pytest tests/python/test_multigraph_algorithms.py tests/python/test_matching_flow_cross_type.py::test_is_biconnected_nx tests/python/test_parity_conformance.py -k 'biconnected' -q`
  reported `8 passed, 235 deselected`.

Baseline direct release timing on a 1000-node / 5000-edge MultiGraph fixture
(1000-cycle + 3000 random edges + 1000 parallel edges, same graph objects for
FNX and NetworkX):

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Baseline verdict |
| --- | ---: | ---: | ---: | --- |
| `is_biconnected` | `12.605 ms` | `2.901 ms` | `0.230x` | loss |
| `articulation_points` | `18.118 ms` | `1.874 ms` | `0.103x` | loss |
| `biconnected_components` | `14.892 ms` | `2.920 ms` | `0.196x` | loss |
| `minimum_spanning_tree` | `29.697 ms` | `9.516 ms` | `0.320x` | loss |
| `bfs_edges(source=0)` | `1.492 ms` | `0.607 ms` | `0.407x` | loss |

Kept route:
- `articulation_points`, `is_biconnected`, `biconnected_components`, and
  `biconnected_component_edges` now walk the MultiGraph's ordered distinct
  adjacency directly instead of materializing a simple `Graph` or delegating
  public `articulation_points` through NetworkX.
- This is the cache-local/CSR-style lever from the optimization pass, but kept
  in exact NetworkX row order: vertex biconnectivity is multiplicity-invariant
  for these contracts, while component-edge output still follows NetworkX's
  `_biconnected_dfs` edge-stack orientation.

RCH Criterion final rows:

| Workload | FNX mean | NetworkX mean | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `is_biconnected` | `0.85370 ms` | `9.0354 ms` | `10.584x` | win |
| `articulation_points` | `0.96998 ms` | `6.3562 ms` | `6.553x` | win |
| `biconnected_components` | `2.1240 ms` | `7.6859 ms` | `3.619x` | win |

Same-process final release sweep on the original baseline fixture:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `is_biconnected` | `1.249 ms` | `2.981 ms` | `2.387x` | win |
| `articulation_points` | `1.337 ms` | `1.950 ms` | `1.459x` | win |
| `biconnected_components` | `1.650 ms` | `2.945 ms` | `1.785x` | win |
| `biconnected_component_edges` | `2.087 ms` | `2.914 ms` | `1.396x` | win |
| `minimum_spanning_tree` | `31.015 ms` | `9.184 ms` | `0.296x` | loss |
| `bfs_edges(source=0)` | `1.668 ms` | `0.666 ms` | `0.399x` | loss |

Decision:
- Keep. Scorecard accounting for this slice: `4` wins / `2` losses / `0`
  neutral on the expanded biconnected/MST/BFS surface; `3` RCH Criterion wins
  for the committed biconnected-family benchmark rows.
- Residual losses are explicit: MultiGraph keyed MST still delegates to
  NetworkX to preserve result type/keys, and `bfs_edges` still loses on this
  particular dense parallel fixture despite prior direct-MultiGraph traversal
  work.

Do not repeat:
- Do not reintroduce `gr.undirected()` simple-Graph materialization for
  MultiGraph biconnected-family queries.
- Do not route public MultiGraph `articulation_points` through NetworkX parity
  delegation for these exact contracts.
- Do not claim the MST row until a keyed MultiGraph MST constructor preserves
  NetworkX type/key/attr semantics and beats the current `0.296x` loss.

## 2026-06-20 MultiDiGraph SCC Stale-Loss Closeout (`br-r37-c1-8hjsu`)

Scope: re-baseline the open `MultiDiGraph` `strongly_connected_components`
loss on current `origin/main` (`cdf8d86d8`) before inventing another SCC
substrate. The current source already contains the direct native
successor-row Tarjan/Nuutila route, so no code was kept or reverted in this
slice.

Environment:
- Agent: `CrimsonRiver` / `cod-b`.
- Worktree: `/data/projects/.scratch/franken_networkx-cod-b-scc-boldverify-20260620`.
- Requested target dir: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Exact requested release install failed with Rust E0514 because that target dir
  contained artifacts from incompatible nightly `beae78130`; no cleanup or file
  deletion was performed.
- Release install used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0-scc`:
  `rch exec -- maturin develop --release --features pyo3/abi3-py310`.
- Per-crate RCH bench/build gate completed:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head multidigraph_connectivity_head_to_head -- --noplot`
  on `vmi1152480`; the retrieved RCH transcript did not include Criterion timing
  rows, so the ratio evidence below comes from the same-process Python harness
  against the freshly installed release extension.
- Focused conformance:
  `pytest tests/python/test_strongly_connected_components_order_parity.py tests/python/test_directed_multigraph_degenerate_parity.py::test_multidigraph_strongly_connected_components_matches_networkx tests/python/test_scc_condensation_invariants.py tests/python/test_networkx_interop_directed_multi.py::test_multidigraph_interop -q`
  reported `212 passed in 1.01s`.

Head-to-head timing on identical 1800-node block/parallel-arc `MultiDiGraph`
with block size `6`, parity checksum matched for every row:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `strongly_connected_components` | `0.642898 ms` | `1.717424 ms` | `2.671x` | win |
| `descendants(source=0)` | `0.457607 ms` | `0.750663 ms` | `1.640x` | win |
| `number_strongly_connected_components` | `0.338000 ms` | `1.542392 ms` | `4.563x` | win |

Decision:
- Keep current code as-is and close `br-r37-c1-8hjsu` as a stale loss. The
  current native SCC route beats NetworkX on the open-loss fixture; no radical
  SCC rewrite is justified by this target.
- Scorecard accounting for this slice: `3` wins / `0` losses / `0` neutral on
  the measured SCC/count/descendant side surface; `1` win / `0` losses /
  `0` neutral for the focused SCC bead row.

Do not repeat:
- Do not reintroduce MultiDiGraph SCC projection through a simple `DiGraph`.
- Do not route public SCC to NetworkX-on-FNX delegation: a quick probe showed it
  is not a native keep and does not improve the release claim.
- Do not clear the shared `cod-b` target dir to fix E0514; use a toolchain-tagged
  target subdir instead.

Next route:
- Remaining open MultiGraph/MultiDiGraph losses are not SCC. Prioritize
  measured residuals such as matrix-exporter sync cost and MultiGraph
  biconnected/MST rows instead of spending more time on this SCC lane.

Scope for the following ledger entry: `br-r37-c1-iyu0a`, multigraph matrix exporters,
`tests/artifacts/perf/20260620T-multigraph-matrix-coo-cc/bench_and_parity.py`.

Environment:
- Agent: `CrimsonRiver` / `cod-b`.
- Target dir: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Release gates: `cargo fmt --check`; `rch exec -- cargo check -p fnx-python --benches`;
  `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`;
  `rch exec -- cargo build --release -p fnx-python`.
- Release install: `maturin develop --release --features pyo3/abi3-py310` with
  fresh target dir `/data/projects/.rch-targets/franken_networkx-cod-b-maturin-clean-f20a92ec0`.
- Parity in every run: `160` configs x `2` exporters, `0` fails, golden SHA
  `bff9639b02900c23d43c585672cddf6a3e39676fa40c631efccec93bfeb44307`.

## 2026-06-20 Multigraph Matrix Exporter Residual

Baseline from `tests/artifacts/perf/20260620T-multigraph-matrix-coo-cc/run.log`:

| Workload | Baseline ratio vs NetworkX | Baseline FNX | Baseline NetworkX |
| --- | ---: | ---: | ---: |
| `to_numpy MultiGraph` | `0.996x` | `2.44 ms` | `2.43 ms` |
| `to_scipy MultiGraph` | `0.863x` | `2.53 ms` | `2.18 ms` |
| `to_numpy MultiDiGraph` | `0.686x` | `7.51 ms` | `5.15 ms` |
| `to_scipy MultiDiGraph` | `0.580x` | `5.92 ms` | `3.44 ms` |

Uncommitted precise dirty-key experiment, reverted before commit:

| Run | Workload | Ratio vs NetworkX | FNX | NetworkX | Verdict |
| --- | --- | ---: | ---: | ---: | --- |
| dirty-key repeat 1 | `to_numpy MultiGraph` | `0.986x` | `2.49 ms` | `2.45 ms` | neutral/loss noise |
| dirty-key repeat 1 | `to_scipy MultiGraph` | `0.853x` | `2.57 ms` | `2.19 ms` | loss |
| dirty-key repeat 1 | `to_numpy MultiDiGraph` | `0.852x` | `6.53 ms` | `5.56 ms` | loss |
| dirty-key repeat 1 | `to_scipy MultiDiGraph` | `0.521x` | `6.66 ms` | `3.47 ms` | loss |
| dirty-key repeat 2 | `to_numpy MultiGraph` | `0.993x` | `2.46 ms` | `2.44 ms` | neutral |
| dirty-key repeat 2 | `to_scipy MultiGraph` | `0.872x` | `2.69 ms` | `2.35 ms` | loss |
| dirty-key repeat 2 | `to_numpy MultiDiGraph` | `0.627x` | `9.52 ms` | `5.97 ms` | loss |
| dirty-key repeat 2 | `to_scipy MultiDiGraph` | `0.476x` | `7.67 ms` | `3.65 ms` | loss |
| dirty-key repeat 3 | `to_numpy MultiGraph` | `0.961x` | `2.69 ms` | `2.58 ms` | loss |
| dirty-key repeat 3 | `to_scipy MultiGraph` | `0.871x` | `2.63 ms` | `2.29 ms` | loss |
| dirty-key repeat 3 | `to_numpy MultiDiGraph` | `0.806x` | `5.84 ms` | `4.71 ms` | loss |
| dirty-key repeat 3 | `to_scipy MultiDiGraph` | `0.551x` | `6.18 ms` | `3.41 ms` | loss |

Clean final run after reverting the dirty-key experiment:

| Run | Workload | Ratio vs NetworkX | FNX | NetworkX | Verdict |
| --- | --- | ---: | ---: | ---: | --- |
| clean repeat 1 | `to_numpy MultiGraph` | `1.090x` | `2.88 ms` | `3.14 ms` | win/noisy |
| clean repeat 1 | `to_scipy MultiGraph` | `0.847x` | `2.87 ms` | `2.43 ms` | loss |
| clean repeat 1 | `to_numpy MultiDiGraph` | `0.579x` | `9.70 ms` | `5.62 ms` | loss |
| clean repeat 1 | `to_scipy MultiDiGraph` | `0.369x` | `11.09 ms` | `4.09 ms` | loss |
| clean repeat 2 | `to_numpy MultiGraph` | `1.003x` | `2.72 ms` | `2.72 ms` | neutral |
| clean repeat 2 | `to_scipy MultiGraph` | `0.882x` | `2.61 ms` | `2.30 ms` | loss |
| clean repeat 2 | `to_numpy MultiDiGraph` | `0.632x` | `8.39 ms` | `5.30 ms` | loss |
| clean repeat 2 | `to_scipy MultiDiGraph` | `0.439x` | `8.35 ms` | `3.66 ms` | loss |
| clean repeat 3 | `to_numpy MultiGraph` | `0.993x` | `2.81 ms` | `2.79 ms` | neutral |
| clean repeat 3 | `to_scipy MultiGraph` | `0.880x` | `2.67 ms` | `2.35 ms` | loss |
| clean repeat 3 | `to_numpy MultiDiGraph` | `0.617x` | `8.75 ms` | `5.40 ms` | loss |
| clean repeat 3 | `to_scipy MultiDiGraph` | `0.447x` | `7.88 ms` | `3.52 ms` | loss |

Decision:
- No code keep from this session. The precise dirty-key experiment was removed
  because it did not produce a stable NetworkX win and still left the biggest
  `MultiDiGraph` exporter row losing.
- The already-committed pure-Python native-COO route is parity-clean but does
  not close the `MultiDiGraph` gap under clean release timing.
- Scorecard accounting for this slice: `0` wins / `3` losses / `1` neutral by
  median clean-repeat workload outcome.

Do not repeat:
- Do not reintroduce the broad dirty-key scaffold without folding it into a
  measured single-pass exporter path.
- Do not claim the `MultiDiGraph` matrix exporter row as a win from self-speedup
  or one noisy `to_numpy` sample.

Next route:
- Fuse finite-weight validation into `adjacency_arrays_multigraph` so the
  default weighted exporter does one native edge pass, not a guard pass plus a
  COO pass.
- Add an integer-index/default-order multigraph COO path only after the fused
  edge-pass route is measured; current evidence suggests stringification is
  secondary.

## 2026-06-20 MultiDiGraph Reverse Copy Dirty-Attr Mirror

Scope: `br-r37-c1-nooou`, `MultiDiGraph.reverse(copy=True)` on a directed
multigraph with 300 nodes, 2936 keyed edges, explicit weights/tags, and a
dirty variant mutating every 31st edge after construction.

Environment:
- Agent: `CrimsonRiver` / `cod-a`.
- Rust target dirs: `/data/projects/.rch-targets/franken_networkx-cod-a-local-check`
  for local release install and
  `/data/projects/.rch-targets/franken_networkx-cod-a-reverify-f20a` for RCH
  release build verification.
- Python `3.13.7`, NetworkX `3.6.1`, `PYTHONHASHSEED=0`, core pinned with
  `taskset -c 4`, 31 timed runs after 8 warmups.
- Release install: `maturin develop --release --features pyo3/abi3-py310`.
- RCH gate: `rch exec -- cargo build --release -p fnx-python`.

Baseline/current-main measurement after the earlier native transpose substrate
showed that the old `0.43x` bead note was stale for the Rust reverse substrate,
but a real dirty Python attr-mirror loss remained:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| clean keyed attrs | 10.200708 ms | 12.005438 ms | 1.177x | win |
| dirty post attrs | 12.148397 ms | 10.310096 ms | 0.849x | loss |

Rejected subattempt:
- Sparse dirty-edge tracking alone reduced the sync surface but still copied
  every Python edge-attr mirror during reverse construction. It was not enough
  to dominate NetworkX.

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| clean keyed attrs | 12.005304 ms | 12.486636 ms | 1.040x | weak/noisy win |
| dirty post attrs | 13.222951 ms | 10.718466 ms | 0.811x | reject |

Kept lever:
- Keep sparse keyed-edge dirty tracking plus lazy reverse-copy edge mirror
  materialization. Lossless edge attr dicts with exact string keys and simple
  scalar values stay in Rust storage until Python asks for the dict; non-lossless
  mirrors and explicitly dirty mirrors are still copied to preserve NetworkX
  object semantics.

| Workload | FNX min | FNX median | FNX p95 | NetworkX min | NetworkX median | NetworkX p95 | Ratio vs NetworkX |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| clean keyed attrs | 5.862346 ms | 7.348492 ms | 8.686637 ms | 9.146017 ms | 9.740804 ms | 10.464004 ms | 1.326x median / 1.560x min |
| dirty post attrs | 6.318381 ms | 7.264913 ms | 8.310785 ms | 8.952791 ms | 9.253100 ms | 9.817109 ms | 1.274x median / 1.417x min |

Post-rebase clean-tree smoke after installing from
`/data/projects/franken_networkx-cod-a-land`:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Digest |
| --- | ---: | ---: | ---: | --- |
| clean keyed attrs | 4.980806 ms | 8.641853 ms | 1.735x | `5987af29b718da04` |
| dirty post attrs | 5.853450 ms | 9.164683 ms | 1.566x | `1d35fe579cedf7b5` |

Parity:
- Clean digest/order hash64: `7657081794215802141`.
- Dirty digest/order hash64: `7376594841975813130`.
- Added non-lossless Python edge-attr parity coverage for tuple attr keys and
  mutable payload object identity.

Gates:
- `cargo fmt --check`
- `cargo check -p fnx-python --benches`
- `cargo clippy -p fnx-python --all-targets -- -D warnings`
- `rch exec -- cargo build --release -p fnx-python`
- focused Python reverse/attr parity: `53 passed`

Decision:
- Keep. This converts the remaining dirty reverse-copy mirror row from `0.849x`
  to `1.274x` vs NetworkX while preserving the clean row as a stronger `1.326x`
  win.
- Scorecard accounting for this slice: `2` wins / `0` losses / `0` neutral for
  the final measured clean and dirty workloads.

Do not repeat:
- Do not claim sparse dirty-key tracking by itself as a keep; it stayed slower
  than NetworkX on the dirty workload.
- Do not rebuild keyed reverse copies through Python per-edge insertion or
  eagerly materialize all Python edge-attr dict mirrors.

## 2026-06-20 Max-Weight Matching Native Tie-Break No-Ship

Scope: `br-r37-c1-lmqwv`, public `max_weight_matching` on a weighted
`gnp(300, 0.05)` simple graph with deterministic integer-like weights. The
public top-level wrapper still delegates to NetworkX for exact matching-choice
and tuple-direction parity. The raw `_fnx.max_weight_matching` blossom kernel
is much faster, but its tie-break policy does not match NetworkX on all tied
maximum-weight optima.

Environment:
- Agent: `CrimsonRiver` / `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-next-20260620T131825Z`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- The requested shared target hit incompatible-rustc E0514 (`cc`,
  `target_lexicon`, and `serde` were compiled by a different nightly). No
  cleanup was performed; release proof runs used fresh target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-20260620`.
- NetworkX oracle: vendored `3.7rc0.dev0`; `PYTHONHASHSEED=0`.

Baseline/current public API and raw native measurement on seed `11`:

| Route | FNX mean | NetworkX mean | Ratio vs NetworkX | Exact edge set | Verdict |
| --- | ---: | ---: | ---: | --- | --- |
| public `fnx.max_weight_matching` delegate | 228.398618 ms | 223.508232 ms | 0.979x | yes | historical loss; superseded |
| raw `_fnx.max_weight_matching` | 5.494071 ms | 223.508232 ms | 40.68x | no | invalid keep |

Raw native exactness sweep:
- Baseline raw canonical/sorted solver route: `4 / 20` seeds differed from
  NetworkX by edge set, with identical total matching weight in every case.
- Full insertion-order candidate/node/edge mapping experiment:
  raw FNX `4.954032 ms` vs NetworkX `225.624950 ms` (`45.54x`) but exact
  mismatches worsened to `6 / 20` seeds (`3, 11, 13, 18, 19, 20`).
- Insertion-order candidates/nodes with restored sorted solver edges:
  raw FNX `6.292802 ms` vs NetworkX `239.127194 ms` (`38.00x`) but exact
  mismatches worsened to `8 / 20` seeds
  (`3, 4, 5, 11, 13, 18, 19, 20`).

Rejected lever:
- Do not route the public wrapper to the existing raw `mwmatching` crate by
  merely changing candidate sorting. The crate derives each vertex's neighbor
  scan order from one global edge sequence, while NetworkX scans each
  adjacency row directly during blossom search. That structural tie-break
  mismatch is enough to choose different valid maximum matchings.

Conformance after reverting the no-ship experiments:
- Focused matching gate:
  `tests/python/test_matching_conformance.py`,
  `tests/python/test_max_weight_matching_tuple_direction_parity.py`, and
  `tests/python/test_flow_cut_matching_value_parity.py` passed
  `184 passed`.

Decision:
- Reject/no-ship for this older session. The public `max_weight_matching` row
  measured as a `0.979x` loss in that run because exact NetworkX tie-break
  parity blocked the raw native `40x+` route.
- Superseded by the 2026-06-21 vendored-oracle remeasure above: the current
  public route is exact and `1.088x` vs NetworkX, so this is no longer an
  active public loss.
- Historical scorecard accounting for this slice: `0` wins / `1` loss /
  `0` neutral.

Do not repeat:
- Do not retry endpoint canonicalization, insertion-order node remapping, or
  solver-edge sorting as standalone fixes for this bead. The next viable route
  is a NetworkX-order blossom port/fork that can scan per-vertex adjacency rows
  exactly, or a formally exact uniqueness-gated native dispatch that declines
  tied-optimum cases before public routing.

## 2026-06-20 Default-Order Multigraph Matrix Exporter Keep + Residual

Scope: `br-r37-c1-iyu0a`, public `to_numpy_array` /
`to_scipy_sparse_array` on exact `MultiGraph` / `MultiDiGraph`, default
`nodelist=None`, `weight="weight"`, and `dtype=None`.

Environment:
- Agent: `CrimsonRiver` / `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-bold-20260620T1345`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- The requested shared target hit incompatible-rustc E0514 (`cc`,
  `target_lexicon`, and `serde` were compiled by a different nightly). No
  cleanup was performed; release proof used fresh target
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-iyu0a-20260620T1349`.
- Post-rebase release install used a second fresh target after the first fresh
  target also hit E0514:
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-iyu0a-postrebase-20260620T1832`.
- NetworkX oracle: vendored import via
  `PYTHONPATH=<worktree>/python:<worktree>/legacy_networkx_code`;
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.

Kept lever:
- Added a default-order native multigraph COO helper that avoids Python
  `list(G)` node canonicalization and reads stored Rust attrs directly when
  `edges_dirty` is false, falling back to live PyDict mirrors when dirty.
- Added a `MultiDiGraph` default-order CSR helper for `format="csr"` that
  pre-sums contiguous parallel edges before constructing the SciPy CSR array.

Baseline in this clean worktree:

| Workload | Baseline ratio vs NetworkX |
| --- | ---: |
| n=500 `to_numpy MultiGraph` | 1.249x |
| n=500 `to_scipy MultiGraph` | 1.136x |
| n=500 `to_numpy MultiDiGraph` | 1.188x |
| n=500 `to_scipy MultiDiGraph` | 0.938x |
| n=2000 `to_numpy MultiGraph` | 0.853x |
| n=2000 `to_scipy MultiGraph` | 0.847x |
| n=2000 `to_numpy MultiDiGraph` | 1.049x |
| n=2000 `to_scipy MultiDiGraph` | 0.645x |

Final measured proof:

| Workload | FNX | NetworkX | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| n=500 `to_numpy MultiGraph` | 1.76 ms | 2.38 ms | 1.352x | win |
| n=500 `to_scipy MultiGraph` | 1.89 ms | 2.18 ms | 1.155x | win |
| n=500 `to_numpy MultiDiGraph` | 2.43 ms | 4.23 ms | 1.741x | win |
| n=500 `to_scipy MultiDiGraph` | 1.99 ms | 3.00 ms | 1.508x | win |
| n=2000 `to_numpy MultiGraph` | 8.199 ms | 7.888 ms | 0.962x | active loss |
| n=2000 `to_scipy MultiGraph` | 6.004 ms | 5.007 ms | 0.834x | active loss |
| n=2000 `to_numpy MultiDiGraph` | 11.797 ms | 13.844 ms | 1.174x | win |
| n=2000 `to_scipy MultiDiGraph` min-of-9 | 8.097 ms | 7.005 ms | 0.865x | active loss |
| n=2000 `to_scipy MultiDiGraph` 50-run min | 5.790 ms | 6.793 ms | 1.173x | noisy win |
| n=2000 `to_scipy MultiDiGraph` 50-run median | 9.290 ms | 8.276 ms | 0.891x | active loss |

Conformance:
- `cargo fmt --check`, `git diff --check`, and
  `python3 -m py_compile python/franken_networkx/__init__.py` passed.
- Per-crate RCH gates passed for `fnx-python`:
  `cargo check -p fnx-python --features pyo3/abi3-py310`,
  `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`,
  `cargo build -p fnx-python --release --features pyo3/abi3-py310`, and
  `cargo bench -p fnx-python --features pyo3/abi3-py310 --no-run`.
- Focused Python exporter suite passed before and after rebase: `604 passed`.
- `ubs` on touched files reached existing file-wide findings in the large
  pre-existing Python/Rust files; no new UBS-specific code issue was kept.
- `tests/artifacts/perf/20260620T-multigraph-matrix-coo-cc/bench_and_parity.py`
  stayed green: `160` configs x `2` exporters, `0` fails, golden
  `bff9639b02900c23d43c585672cddf6a3e39676fa40c631efccec93bfeb44307`.
- Focused dirty finite-weight mutation parity for default-order
  `MultiDiGraph` dense/CSR/COO paths passed before the nonnumeric fallback
  probe hit a pre-existing exception-class mismatch outside this fast path.

Rejected sub-levers:
- Broadly enabling the default-order helper for undirected `MultiGraph` at
  larger scale regressed `to_scipy MultiGraph` (`0.777x` on the n=2000 probe);
  final Python dispatch is narrowed to `MultiDiGraph` for the new default-order
  helpers.
- A streaming-successor CSR rewrite that avoided `edges_ordered_borrowed()`
  regressed the n=500 fixture (`to_scipy MultiDiGraph` fell to `0.808x`) and
  was manually reverted.

Decision:
- Keep as a measured partial closeout for the original default-order
  n≈400/500 matrix-exporter gap: `4` wins / `0` losses / `0` neutral on the
  artifact harness.
- Do not claim large-scale sparse domination: n=2000 sparse median rows remain
  active losses and need a deeper boundary/layout route.

Do not repeat:
- Do not re-enable the undirected `MultiGraph` default-order helper without a
  new large-scale undirected sparse proof.
- Do not retry the streaming-successor CSR accessor path; the allocated
  `edges_ordered_borrowed()` version is the measured keep.
- Next route for the residual: reduce PyO3 Vec-to-NumPy handoff cost or add a
  native array/CSR buffer boundary for large sparse multigraph exporters.

## 2026-06-20 `volume(G, S)` native-binding routing rejected (`br-r37-c1-volnative`, BlackThrush)

Scope: the public `volume(G, S)` cut-metric wrapper. Direct same-process timing
vs NetworkX 3.6.1 on `barabasi_albert_graph(2500, 3, seed=1)` showed the current
full-degree-dict fast path (`deg = dict(G.degree()); sum(deg.get(v,0) for v in S)`)
loses because it scales with `|V|`, not `|S|`: `|S|=250` `0.15x`, `|S|=1250`
`0.62x`, `|S|=2250` `0.95x` (it builds all 2500 degrees just to sum a subset).

Attempt: route exact fnx simple `Graph` inputs to the native `_fnx.volume`
binding. The shared core `fnx_algorithms::volume` kernel counts an undirected
self-loop ONCE (it is also used by `conductance`, so it was left untouched);
NetworkX's `sum(G.degree(v) for v in S)` counts each self-loop TWICE. Fixed this
in the binding with an `O(|S|)` `Graph::degree` sum (row length + self-loop probe,
already nx-correct) over the distinct nodes of `S`. Byte-exact vs NetworkX:
`1500/1500` random graphs including self-loops, missing nodes (degree 0),
generator `S`, and empty `S`.

Result: `0.86x` / `0.80x` / `0.76x` at `|S|=250/1250/2250` — STILL A LOSS, and the
large-`S` row regressed vs the full-dict path (`0.95x -> 0.76x`). Root cause: the
binding pays `node_key_to_string` (Python object -> canonical String) per node in
`S`, an `O(|S|)` conversion tax that NetworkX's native Python-dict `degree(nbunch)`
view avoids; that tax dominates a sub-millisecond degree-sum. Measured under host
load 13+, but the loss is structural, not noise.

Verdict: reverted (`~0-gain`, no clear win at any `|S|`). `volume` is
String-conversion-substrate-bound, the same class as multigraph copy/to_undirected.

Do not retry:
- Do not route `volume`/degree-sum-over-nbunch ops through the per-node
  `node_key_to_string` native binding; the String-conversion tax exceeds the
  degree-sum it replaces.
- Do not change the shared core `fnx_algorithms::volume` kernel's single self-loop
  count (it feeds `conductance`); any volume self-loop fix belongs in a caller.
- Next viable route would need a Python-object-native or integer-index degree-sum
  that skips canonical String conversion entirely.


## 2026-06-20 MultiGraph/MultiDiGraph `bfs_edges` pinned re-measure (`br-r37-c1-1jm15`, BlackThrush)

Pinned (`taskset -c 2`, `PYTHONHASHSEED=0`, warm min-of-40) on the bead's exact
`MultiGraph(1000 nodes, 5000 edges)` fixture, fresh release build at `8b459515f`:

- `MultiGraph.bfs_edges(0)`: FNX `0.50 ms` vs NetworkX `0.51 ms`, `1.01x` across 3
  pinned trials (edge sequence identical, 999 edges). The `0.825x` recorded when
  `1jm15` was split does NOT reproduce — a later build flipped it to parity. The
  bead is effectively RESOLVED; recommend a pinned confirm + close.
- `MultiDiGraph.bfs_edges(0)` (same shape): FNX `0.507 ms` vs NetworkX `0.425 ms`,
  `0.84x` — a real residual. 100% in the native `_fnx.bfs_edges` kernel (cProfile:
  zero Python overhead beyond the per-edge generator). Root cause is the
  String-keyed directed-multigraph successor BFS substrate (the MultiGraph kernel
  is already at parity), i.e. the same int-CSR migration class peers recorded as
  no-ship for multidigraph CSR. Not a contained win.

Do not retry:
- Do not chase `MultiGraph.bfs_edges` as a loss without a pinned re-measure first;
  it is at parity on the current build.
- Do not micro-tweak the `MultiDiGraph.bfs_edges` kernel for the `0.84x` residual;
  it is String-keyed-successor-substrate-bound, only an integer-CSR MultiDiGraph
  adjacency would move it (deferred, peer-confirmed no-ship class).

## 2026-06-20 `all_pairs_node_connectivity(nbunch=[few])` small-subset delegation tax (`br-r37-c1-apncnbunch` residual, BlackThrush)

Pinned (`taskset -c 2`, `PYTHONHASHSEED=0`, min-of-12) on `Graph(400 nodes, 1600
edges)`, `nbunch=[0,1,2]`: FNX `17.8 ms` vs NetworkX `14.4 ms`, `0.81x`, parity
true. The wrapper already (correctly) delegates a small nbunch (`<= |V|/2`) to nx
because the native `all_pairs_node_connectivity_rust` computes the FULL `O(V^2)`
pair set regardless of nbunch (a 4-node nbunch on n=120 was `2839 ms` vs nx `6 ms`).
So the residual `0.81x` is the `fnx->nx` whole-graph conversion the delegation pays
before nx runs only `C(k,2)` flows on one reused auxiliary graph.

Dead-ends confirmed (do not retry):
- There is NO correct native per-pair local node-connectivity binding:
  `_fnx.node_connectivity(g)` is GLOBAL-only; passing `(g, u, v)` SILENTLY returns
  garbage (`_fnx.node_connectivity(g,0,2)=0` where nx local `(0,2)=3`) — the `u,v`
  args are ignored. Per-pair routing diverges 52/200. (Latent binding foot-gun.)
- Using the bulk `all_pairs_node_connectivity_rust` for a small nbunch is far
  worse (full `O(V^2)` flows).

Only viable lever (substantial, not a verify-quick win): either add an
nbunch-restricted native kernel that builds the auxiliary node-connectivity digraph
once and runs only the `C(k,2)` requested max-flows, or reimplement nx's
`build_auxiliary_node_connectivity` + `local_node_connectivity` in-process over fnx
adjacency to skip the `fnx->nx` conversion (max-flow tie-break parity required).

## 2026-06-20 Delegation-tax root cause: `_fnx_to_nx` conversion is 5x `nx.Graph(edges)` (BlackThrush)

Context for the residual small-input delegation losses (e.g. all_pairs_node_connectivity
above). Pinned (`taskset -c 2`): `_networkx_graph_for_parity` -> `backend._fnx_to_nx`
costs `3.1 ms` (n=400) / `16.4 ms` (n=1500/7000e) vs `nx.Graph(g.edges())` `0.73 ms` /
`3.4 ms` — ~5x. cProfile of `_fnx_to_nx` (n=1500): body `9.8 ms` + nx `add_edges_from`
`5.8 ms` + native `fnx_to_nx_adjacency` `2 ms` + `_align_rows` `2 ms`; ~500k `dict.update`
+ 254k `dict.get` per 30 calls.

Why it is NOT a verify-quick win:
- The body cost is dominated by (a) the parity-REQUIRED adjacency-row alignment
  (`_align_inline`/`_align_rows` reorder nx `_adj`/`_succ`/`_pred` rows to match fnx
  insertion order — REQUIRED or every order-dependent delegated algo diverges:
  greedy_color, ego_graph, BFS/DFS variants) and (b) the canonical-key -> original-
  Python-object remap (the native bulk returns interned canonical strings, not the
  user's node objects). Both are inherent to faithful delegation, not waste.
- The node-attr materialization (`dict(node_view[node])` per node) is only `0.39 ms`
  of the `16.4 ms` (gating it on the cheap native `graph_has_any_attrs` saves ~3%,
  i.e. ~0-gain), so it is NOT worth a critical-path edit.
- Per-function payoff is small: the delegated algorithm usually dominates; halving
  the conversion would still leave all_pairs_node_connectivity(small nbunch) a loss.

Do not retry: do not micro-tweak `_fnx_to_nx` (node-attr skip, etc.) for the delegation
tax — the gain is ~0 and the blast radius (175 delegating functions) is large. A real
lever would need the native bulk crossing to emit original node objects AND
pre-aligned rows so the Python remap+align passes disappear entirely.

## 2026-06-20 `within_inter_cluster` bulk-community pre-fill REVERTED (net regression) (`br-r37-c1-wicbulk`, BlackThrush)

`within_inter_cluster` (cut/link-prediction gauntlet, `within_inter_cluster_explicit_community`)
on `Graph(400, 2000)` measured `0.54-0.61x` for a small explicit ebunch (50 pairs).
Profiling blamed the per-node `G.nodes[w][community]` AtlasView read (vars/
_private_override/__getitem__) over every ebunch endpoint AND common neighbor.

Attempt: pre-fill the community cache in ONE bulk `nodes(data=community, default=MISS)`
crossing (exact Graph only), raise lazily on first MISS access. Byte-exact 800/800
incl default/explicit/missing-community.

Pinned A/B (`taskset -c 2`, same window) — NET REGRESSION:
- default ebunch (non_edges) n=200: `1.74x -> 1.55x` (WORSE)
- 500-pair explicit: `1.57x -> 1.52x` (WORSE)
- 50-pair explicit: `0.56x -> 0.61x` (better, the only win)

Root cause: the existing per-node community_cache ALREADY amortizes repeated access
(each distinct node read once, then cached), so the bulk read only helps when the
ebunch+common-neighbors touch ~all of V AND each node is read once — which the cache
already covers. The bulk read of all |V| communities is pure overhead when the
accessed set < |V| (concentrated ebunch), and the added per-call `is _WIC_MISSING`
branch taxes the O(V^2) default path. REVERTED per ~0-gain/regression.

Do not retry: do not bulk-prefill node attrs for within_inter_cluster (or similar
already-cached per-node-attr link-prediction scorers) — the lazy cache wins. The
50-pair gap is the irreducible `G.neighbors` PyO3 per-node cost vs nx's dict (raw
neighbors measured SLOWER, 158us vs 122us).

## 2026-06-20 I/O sweep: `adjacency_data` attr-heavy residual (substrate) + `tree_data` FIXED (BlackThrush)

Pinned I/O sweep (`taskset -c 2`) found two losses; `tree_data` fixed (commit
aedc783ed, 0.40x -> 1.12x via bulk adjacency/attr snapshot + transpose-pred). The
other:
- `adjacency_data(Graph, attr-heavy)` `0.79x` (1.758ms vs nx 1.383ms) — but the
  native `_fnx.adjacency_data_simple` fast path IS already used (returns non-None);
  no-attr is `1.19x`. The attr-heavy residual is the native per-edge attr-dict
  CONSTRUCTION (PyO3) being slower than nx's C dict copy — the same
  view-materialization substrate as `nodes(data=attr)` 0.20x / `dict(adjacency())`.
  NOT a contained win (the native kernel is already the path; the gap is the
  Python-dict-from-Rust materialization floor).

Rest of the I/O surface WINS or neutral (pinned): generate_edgelist 1.30x,
parse_edgelist 1.72x, to_dict_of_lists 1.91x, node_link_data 1.28x, generate_gml
0.98x, generate_graphml 0.98x, cytoscape_data 0.97x, parse_adjlist 1.14x.

Do not retry adjacency_data attr-heavy: the native fast path is already used; the
residual needs the broader Rust-dict-to-Python materialization lever (persistent
ordered Python adj/attr mirror), not a kernel tweak.

## 2026-06-20 Serialization sweep round 2: tree_graph + cytoscape_graph FIXED; attr_matrix residual (BlackThrush)

Reconstruction functions rebuilt graphs via per-element add_node/add_edge +
view.update PyO3 round-trips (construction tax). Batch lever (collect tuples ->
add_nodes_from/add_edges_from) shipped two WINS:
- tree_graph (3797accdf): no-attr 0.42x -> 1.15x, attr 0.40x -> 0.88x.
- cytoscape_graph (90389ed97): 0.27x -> 1.26x (7.8x self).
(node_link_graph 1.42x / adjacency_graph 1.61x already batched.)

Confirmed real residual:
- attr_matrix(Graph, default) `0.51x` (pinned). The vectorised COO fast path
  (br-r37-c1-attrmtxcoo) IS already hit; cProfile: native adjacency_nodelist_typed_arrays
  0.53ms + np.asarray list->array conversion 0.48ms + zeros + np.add.at. The
  np.asarray cost is the native returning Python lists not numpy arrays; even
  eliminating it lands ~0.78x (still a loss) vs nx's tight per-edge scatter loop.
  NOT a contained win — needs the native binding to emit numpy arrays directly
  (rust-numpy), and even then marginal.

NOISE CORRECTION: the round-1 I/O sweep ran under host load 27.6; its smaller-margin
"losses" were noise — re-verified pinned (load ~10): to_pandas_adjacency 1.09-1.13x
(WIN, memory was right), to_numpy_array 1.08-1.12x, cytoscape_data 1.01x,
generate_multiline_adjlist 0.94x, pajek 0.86x (borderline). Only tree_graph 0.44x /
cytoscape_graph 0.27x (big margins) survived noise and were real (now fixed).
LESSON: trust only big-margin sweep losses under high load; re-verify pinned.

## 2026-06-20 stochastic_graph partial keep — copy fix 0.34x -> 0.64x (still loss) (br-r37-c1-stochcopy, BlackThrush)

stochastic_graph(DiGraph) was 0.34x nx. cProfile: the cost was `_copy_graph_shallow`
rebuilding the copy via a per-edge `add_edge` loop (3200 add_edge calls = the
construction tax), NOT the weight passes. KEPT: for an exact DiGraph use the native
integer-CSR `G.copy()` (independent attr dicts; verified the in-place weight
normalisation stays isolated from G) and materialise the edge view ONCE (live
attr-dict refs) instead of two `edges(data=True)` crossings. Multigraph keeps
`_copy_graph_shallow` (native multi-copy is the slow String-keyed path); subclasses
keep it.

Pinned best-of-60 x5 (load ~14): 0.34x -> median 0.64x (~1.9x self-speedup), still a
vs-nx LOSS. Residual: even one `edges(data=True)` materialisation + the native copy
is slower than nx's plain-dict copy + 2 dict passes — the edges(data=True) view
materialisation floor ([[reference_warm_saturation_map_and_coldeig_noise]] nodes/adj
view substrate). MultiDiGraph stays ~0.38x (slow multigraph copy substrate). Parity
600/600 (simple+multi, copy T/F, no-weight edges, original-unchanged); pytest -k
stochastic 8 passed. KEEP PARTIAL (real self-speedup); full win needs the persistent
ordered Python adj/attr mirror (edges(data=True) floor) or a native stochastic kernel.

## 2026-06-20 Target-Specific `single_source_dijkstra` Early-Exit Keep (`br-r37-c1-04z53`, cod-b)

Scope: recover the weighted directed Dijkstra residual before trying another
path-emission micro-lever. Current source already closed the historical
all-target `br-r37-c1-0opkc` n=1400/n=2600 losses, but
`single_source_dijkstra(G, source, target=t, weight="weight")` still routed
through the all-target raw binding and built every distance/path before
returning one target.

Environment:
- Agent Mail identity and CLI actor: `CrimsonRiver`; bead assignee `cod-b`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-boldverify-20260621T0015`.
- Requested RCH target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  passed on `vmi1149989` with the requested target rewritten to a worker-scoped
  path.
- Local release install against the requested target hit incompatible-rustc
  E0514 from stale artifacts. No cleanup, deletion, or reset was performed.
  The local extension install used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-boldverify-f20a92ec0`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`,
  `taskset -c 4`.

Lever:
- For `single_source_dijkstra` with a concrete `target`, no `cutoff`, and a
  string `weight`, dispatch to the existing native
  `_fnx.dijkstra_path_to_target` binding.
- Preserve current semantics for `cutoff`, callable/non-string weights,
  delegated negative/nonfinite/nonnumeric weights, and missing targets.

Baseline observations:
- Current all-target `single_source_dijkstra` is no longer the `0opkc` active
  loss: n=1400 all-int `1.337x`, n=1400 mixed `1.821x`, n=2600 all-int
  `1.466x`, and n=2600 mixed `2.849x` vs NetworkX on the live fixture.
- Pre-patch target-specific rows still lost on the target surface:
  n=1400 mixed-near `0.750x`, n=1400 all-int far `0.178x`, n=1400 mixed far
  `0.196x`, n=2600 all-int near `0.167x`, and n=2600 all-int far `0.371x`.

Final direct-loop evidence:

| Workload | FNX p50 | NetworkX p50 | Ratio vs NetworkX | Digest |
| --- | ---: | ---: | ---: | --- |
| n=1400 all-int target-near | `2.058399 ms` | `3.230062 ms` | `1.569x` | `655c27bc64a0bf4d7315015c1593026d1a4872fe51bfc3d217e82f85765967be` |
| n=1400 all-int target-far | `0.104427 ms` | `0.478805 ms` | `4.585x` | `986783df8d6c8978123962b628a06959c181bcbf99798fcdaa02be4739692442` |
| n=1400 mixed target-near | `0.329712 ms` | `1.996522 ms` | `6.055x` | `d9aad48926eca4baa01cb9d16f8fab1263406baa415f9d87cd73b7878e068d2d` |
| n=1400 mixed target-far | `0.096642 ms` | `0.573694 ms` | `5.936x` | `20f52f9afcdd26e41894c56ed93948cbabcc4a6c3a82e62b1561526b33a130db` |
| n=2600 all-int target-near | `0.278847 ms` | `1.043872 ms` | `3.744x` | `55e9ec91ca54587e55fdfe943e7066055cb43a148af33458f099aeb32f54925b` |
| n=2600 all-int target-far | `0.253389 ms` | `1.345772 ms` | `5.311x` | `f3fcb25105323d42a4a852b17d8a27be65de3376e9504cac6f8890093aa0f432` |
| n=2600 mixed target-near | `4.081119 ms` | `8.419554 ms` | `2.063x` | `d776a460c8a4f7e82a0e7231f5e2d300262586effa28f62f439d3c09163baa53` |
| n=2600 mixed target-far | `0.952880 ms` | `4.902420 ms` | `5.145x` | `89c4424c00f59aadeada968f57088fb1d9518eabeab1247208370768746c0610` |

Batched same-process keep gate:

| Workload | Old raw-all-path p50 | New p50 | NetworkX p50 | New vs NetworkX | New vs old |
| --- | ---: | ---: | ---: | ---: | ---: |
| n=1400 all-int far | `2.684641 ms` | `0.103329 ms` | `0.779869 ms` | `7.547x` | `25.982x` |
| n=1400 mixed far | `3.828867 ms` | `0.126583 ms` | `0.559703 ms` | `4.422x` | `30.248x` |
| n=2600 all-int near | `4.805508 ms` | `0.232390 ms` | `0.981963 ms` | `4.226x` | `20.679x` |
| n=2600 all-int far | `6.262417 ms` | `0.239303 ms` | `1.079285 ms` | `4.510x` | `26.169x` |
| n=2600 mixed far | `5.927624 ms` | `0.617956 ms` | `4.224094 ms` | `6.836x` | `9.592x` |

Conformance and gates:
- Parity digests matched for every direct-loop and batched row.
- `python -m py_compile python/franken_networkx/__init__.py` passed.
- Focused shortest-path pytest passed: `159 passed`.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed
  on `vmi1152480`.

Decision:
- Keep. Target-specific score is `8` wins / `0` losses / `0` neutral vs
  NetworkX.
- Stale-loss closeout: the live all-target `0opkc` n=1400/n=2600 rows are no
  longer active losses on current source.

Do not repeat:
- Do not route target-specific `single_source_dijkstra` through full all-target
  distance/path emission when the native target kernel is available.
- Do not retry standalone display-key cache or `PyList::new` path streaming for
  this surface; the live target loss was dispatch shape, not all-target path
  emission.
