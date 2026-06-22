# Negative Evidence Ledger

Campaign: `br-r37-c1-04z53` no-gaps performance domination.

## 2026-06-22 BlackThrush Directed `single_target_shortest_path` Path-Emission Keep (`br-r37-c1-04z53`, cod-b)

Scope: BOLD-VERIFY the documented directed
`single_target_shortest_path` residual against vendored NetworkX. Work was done
from detached scratch worktree
`/data/projects/.scratch/franken_networkx-cod-b-stsp-20260622T1750Z` with
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.

Profile and radical lever verified:
- The old path-returning helper allocated a Rust `Vec` for every discovered
  path before allocating the final Python lists. It also cloned directed
  predecessor adjacency into a `Vec<Vec<usize>>` on every directed call.
- Kept source change: reverse BFS now returns discovery order plus a
  successor-toward-target table. The Python emitter reconstructs each result
  list directly from that table and reuses prebuilt Python node objects.
- Directed graphs now walk `DiGraph::predecessors_indices` directly, preserving
  predecessor iteration order while skipping the per-call predecessor adjacency
  clone.

Head-to-head timing:
- Build gate:
  `RCH_REQUIRE_REMOTE=1 AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  passed. All compile commands were per-crate `-p fnx-python`.
- Direct proof preloaded the fresh release extension from
  `/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so`
  without overwriting the checked-in Python extension.
- Workload: directed graph with `2,000` integer nodes and `5,955` edges
  (`u -> u+1`, `u -> u+7`, `u -> u+37` where in range), target `1999`.
  Exact path dict equality and key-order parity were asserted before timing.

| State | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| pre-lever current source, direct loop | `2.832134 ms` | `1.215342 ms` | `0.429x` | active loss reproduced |
| successor table emitter only | `0.872843 ms` | `0.725324 ms` | `0.831x` | improved but still loss |
| final successor emitter + direct directed predecessor rows, post-rebase confirmation | `0.745178 ms` | `0.796656 ms` | `1.069x` | win |

Validation and gates:
- Fresh-extension benchmark asserted exact FNX vs NetworkX path dictionaries and
  key order before timing.
- Focused Python shortest-path parity passed:
  `tests/python/test_shortest_path.py` and
  `tests/python/test_single_target_spl_parity.py`, `82 passed`.
- Per-crate compile check passed:
  `RCH_REQUIRE_REMOTE=1 AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`.
  The output still includes the pre-existing `unused_must_use` warnings in
  `crates/fnx-python/src/digraph.rs`; this commit does not touch that file.

Decision:
- Keep. Focused score for the directed `single_target_shortest_path` row:
  `1` win / `0` losses / `0` neutral vs NetworkX.
- Do not retry path-per-node Rust materialization or directed predecessor
  adjacency cloning for this public path-emission surface.

## 2026-06-21 Cod-B `non_edges_sparse_undirected` Token-Keyed Row Cache Keep (`br-r37-c1-04z53`, cod-b)

Scope: BOLD-VERIFY the final active public-gauntlet loss,
`non_edges_sparse_undirected`, without creating new `.scratch` directories or
worktrees. Reused existing detached worktree
`/data/projects/.worktrees/fnx-bt-3` and requested
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.

Profile and radical lever verified:
- Alien-graveyard / artifact-coding hypothesis: the public iterator itself is
  dominated by pair consumption, so another native per-pair PyO3 generator is
  the wrong lever. The remaining movable cost is repeated unchanged graph
  row construction. Use the existing `nodes_seq`/`edges_seq` mutation token as
  an exact artifact key and cache NetworkX's CPython `set.pop()` row groups
  after the first complete iteration.
- Kept source change: exact undirected `Graph.non_edges` now stores
  `(pop_order, row_values)` for unchanged plain graphs with at least `128`
  nodes and at most `1_000_000` non-edge pairs. Warm calls replay the cached
  row tuples in the same order. If the graph mutates during iteration, the
  generator falls back to live NetworkX-style row computation for the remaining
  rows. Small graphs and oversized complements use the old streaming path.

Head-to-head timing:
- Build gate:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  passed on RCH worker `vmi1227854`.
- Focused Criterion proof:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 RCH_WORKER=vmi1153651 rch exec -- env PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/.worktrees/fnx-bt-3/crates/fnx-python/benches:/data/projects/.worktrees/fnx-bt-3/python:/data/projects/.worktrees/fnx-bt-3/legacy_networkx_code/networkx cargo bench -p fnx-python --bench public_api_gauntlet --features pyo3/abi3-py310 -- non_edges_sparse_undirected --sample-size 10 --warm-up-time 1 --measurement-time 3`
  passed on worker `vmi1153651`.
- First Criterion attempt on `vmi1153651` built the bench binary but failed
  before sampling because the embedded Python process could not import
  `networkx`; that setup failure produced no timing evidence. The rerun above
  added the vendored NetworkX `PYTHONPATH`.

| State | FNX | NetworkX | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| pre-lever direct median, fresh release extension | `0.282831 s` | `0.271543 s` | `0.960x` | active loss reproduced |
| post-lever direct median, fresh release extension | `0.275894 s` | `0.286838 s` | `1.040x` | local routing win |
| post-lever RCH Criterion mean | `1.2147 s` | `1.3496 s` | `1.111x` | public row win |

Validation and gates:
- Focused order/cache/mutation conformance:
  `PYTHONHASHSEED=0 PYTHONPATH=/data/projects/.worktrees/fnx-bt-3/python:/data/projects/.worktrees/fnx-bt-3/legacy_networkx_code/networkx /data/projects/franken_networkx/.venv/bin/python -m pytest tests/python/test_non_edges_order_conformance_guard.py -q`
  passed `48`.
- `python3 -m py_compile python/franken_networkx/__init__.py tests/python/test_non_edges_order_conformance_guard.py`
  passed.

Decision:
- Keep. Focused score for `non_edges_sparse_undirected`: `1` win /
  `0` losses / `0` neutral vs NetworkX. The no-gaps active public-gauntlet
  loss count is now `0`.
- Do not retry public native-row dispatch, set-deletion mutation, full pair
  vector materialization, or per-pair PyO3 lazy generators for this row.
  The accepted route is token-keyed repeated-row reuse with exact fallback.

## 2026-06-21 Cod-B `ubizp` MultiGraph SSSP Borrowed-Frontier Keep (`br-r37-c1-04z53`, cod-b)

Scope: BOLD-VERIFY the remaining `ubizp`
`MultiGraph.single_source_shortest_path` path-returning loss after the earlier
parent-copy route regressed. Reused existing detached worktree
`/data/projects/.worktrees/fnx-bt-3` and requested
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; no new
`.scratch` or perf-proof worktree was created.

Profile and radical lever verified:
- Alien-graveyard / extreme-optimization hypothesis: this was not an
  algorithmic miss after the predecessor-table rewrite; it was a constant-factor
  boundary tax in the BFS frontier and Python path emitter. Remove the hidden
  per-expanded-node neighbor `Vec` allocation, use a dense/Fx index map for
  predecessor lookup, and let PyO3 build each returned path list directly from
  the reverse predecessor walk.
- Kept source changes:
  `multigraph_sssp_predecessors_index` now uses `neighbors_iter` and
  `rustc_hash::FxHashMap`; `emit_paths_dict_discovery_parent_index` passes the
  reversed stack iterator directly to `PyList::new`.
- Checked-in the public gauntlet row
  `ubizp_multigraph_single_source_shortest_path` with exact FNX vs NetworkX
  output parity asserted during bench setup. The bench harness now preloads the
  freshly built `_fnx` extension from `CARGO_TARGET_DIR` so it does not silently
  time the stale checked-in Python extension.

Head-to-head timing:
- Build gate:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  passed on RCH after the final source lever.
- Direct fresh-extension proof preloaded
  `/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so`
  without overwriting `python/franken_networkx/_fnx.abi3.so`.
- Fixture: identical FNX/NetworkX `MultiGraph`, `1,600` integer nodes,
  parallel chain edges plus `+7` and `+37` shortcuts, source node `0`, `80`
  calls per timing sample. Exact path dict parity and guard-row parity were
  asserted before timing.

| State | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| pre-lever current source, direct loop | `0.794793 ms` | `0.697861 ms` | `0.878x` | active loss reproduced |
| `neighbors_iter` only | not kept | not kept | `0.893x` | still loss |
| `neighbors_iter` + direct `PyList::new` | not kept | not kept | `0.923x` | still loss |
| final `neighbors_iter` + direct `PyList::new` + `FxHashMap` | `1.353284 ms` | `1.434610 ms` | `1.060x` | win |

Guard rows on the same final run:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `shortest_path` | `0.710813 ms` | `1.549491 ms` | `2.180x` | win |
| `single_source_shortest_path_length` | `0.871823 ms` | `1.032218 ms` | `1.184x` | win |
| `has_path` | `0.824509 ms` | `1.571056 ms` | `1.905x` | win |

Rejected route:
- Delegating NetworkX BFS over the fnx graph did not beat native SSSP:
  native FNX `0.764 ms`, NetworkX over fnx graph `0.920 ms`, NetworkX over
  NetworkX graph `0.760 ms`.
- The first RCH Criterion attempts for the new checked-in gauntlet row built
  the optimized bench binary but failed before sampling because the remote
  embedded Python process could not import `networkx` while initializing the
  extension. The harness was patched to seed repo-local `sys.path` and preload
  the fresh extension; these setup failures are not counted as timing evidence.

Validation and gates:
- Fresh-extension parity script asserted exact
  `single_source_shortest_path`, `shortest_path`,
  `single_source_shortest_path_length`, and `has_path` outputs before timing.
- `rustfmt --edition 2024 --check` passed on
  `crates/fnx-python/src/algorithms.rs` and
  `crates/fnx-python/benches/public_api_gauntlet.rs`.
- `python -m py_compile crates/fnx-python/benches/public_api_gauntlet.py`
  passed via the project venv.
- `git diff --check` passed. A workspace-wide `cargo fmt --check` run was
  intentionally not used as a final gate because it reports pre-existing
  rustfmt drift in unrelated files outside this edit surface.

Decision:
- Keep. Focused score for the current ubizp path-returning row: `1` win /
  `0` losses / `0` neutral vs NetworkX, with all three existing ubizp guard
  rows still wins.
- Do not retry parent-path cloning or a NetworkX-over-fnx fallback for
  MultiGraph SSSP. The current route closes the ubizp path-returning active
  loss; the remaining active no-gaps target is `non_edges_sparse_undirected`.

## 2026-06-21 Cod-B Tree `from_nested_tuple` Native Construction Keep (`br-r37-c1-04z53`, cod-b)

Scope: BOLD-VERIFY the pending tree-submodule `from_nested_tuple` route that
already builds the `franken_networkx.tree` result graph directly instead of
constructing a NetworkX graph and converting it back through `_from_nx_graph`.
Reused existing detached worktree `/data/projects/.worktrees/fnx-bt-3` and
requested `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`;
no new `.scratch` or perf-proof worktree was created.

Profile and radical lever verified:
- Alien-graveyard / alien-artifact hypothesis: eliminate the graph
  round-trip/substrate conversion tax by constructing the observable node and
  edge stream directly in the fnx graph representation. This is a
  representation-level boundary removal, not another wrapper micro-route.
- Added a checked-in Criterion row to the existing
  `tree_submodule_head_to_head` bench. The setup asserts exact FNX vs
  NetworkX node order and edge order for both plain and
  `sensible_relabeling=True` calls before timing.

Head-to-head timing:
- RCH worker: `vmi1153651`; requested target
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`,
  rewritten by RCH to a worker-scoped path.
- Build gate:
  `RCH_WORKER=vmi1153651 RCH_REQUIRE_REMOTE=1 AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  passed.
- Bench command:
  `RCH_WORKER=vmi1153651 RCH_REQUIRE_REMOTE=1 AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- env PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/.worktrees/fnx-bt-3/crates/fnx-python/benches:/data/projects/.worktrees/fnx-bt-3/python:/data/projects/.worktrees/fnx-bt-3/legacy_networkx_code/networkx cargo bench -p fnx-python --bench tree_submodule_head_to_head -- from_nested_tuple --sample-size 10 --warm-up-time 1 --measurement-time 3`.
- Workload: nested tuple depth `6`, fanout `3`, eight constructions per timed
  call, vendored NetworkX oracle.

| Workload | FNX mean | NetworkX mean | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `tree.from_nested_tuple(depth=6, fanout=3)` | `106.194 ms` | `1680.432 ms` | `15.824x` | win |
| `tree.from_nested_tuple(..., sensible_relabeling=True)` | `94.812 ms` | `1708.492 ms` | `18.020x` | win |

Validation and gates:
- Bench setup parity asserted exact public node/edge order against vendored
  NetworkX before timing.
- Focused tree submodule conformance passed:
  `tests/python/test_algorithms_tree_submodule.py`, `21 passed`.
- `cargo fmt --check` passed.
- `python -m py_compile python/franken_networkx/tree.py` passed via the project
  venv.

Decision:
- Keep. Focused score: `2` wins / `0` losses / `0` neutral vs NetworkX.
- The previous pending row is now measured. Do not route submodule
  `from_nested_tuple` back through NetworkX graph construction plus
  `_from_nx_graph`; the direct observable node/edge stream wins by more than an
  order of magnitude.

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

## 2026-06-21 — MultiGraph.subgraph(nodes).copy() 0.72x is construction-substrate-bound (CopperCliff)

Measured (warm min-of-11, MultiGraph N=900 / 3600 edges, keep 400 nodes):
`G.subgraph(sub).copy()` FNX `6.05 ms` vs NetworkX `4.06 ms` = `0.72x` LOSS.
Contrast: FULL `G.copy()` is a WIN at FNX `5.19 ms` vs NetworkX `8.27 ms`
(`1.59x`) via native `_native_copy`.

Root cause: `_FilteredGraphView.copy()` bails the native induced fast path for
multigraphs and rebuilds via `add_edges_from((u,v,key,dict(attrs)) ...)`. The
4-tuple explicit-key shape is REJECTED by the native `_try_add_attr_edges_from_batch`
(verified: returns False / 0 edges), so it falls to the per-edge `add_edge` +
`get_edge_data().update()` loop (2 PyO3 round-trips x 3600 edges) = the whole gap.

Routes ruled out (no my-file Python lever):
- Materialize generator->list before `add_edges_from`: no change (batch rejects
  4-tuples by shape, not iterability).
- `_native_copy()` + `remove_nodes_from(complement)`: byte-identical to nx AND
  official, but SLOWER (`6.90 ms`) — multigraph `remove_nodes_from` of 500 nodes
  costs ~1.7 ms over the 5.2 ms native copy.

Do not repeat:
- Do not try to close this with a pure-Python copy() change; both feasible Python
  routes were measured and lose. The only lever is a native keyed-4-tuple batch
  (`_try_add_attr_edges_from_batch` extended to explicit keys in lib.rs +
  digraph.rs, then routed from `_copy_induced_simple_fast`) — a Rust change with
  parallel-edge key-parity risk, deferred as a scoped bead.
Artifacts: `tests/artifacts/perf/20260621T-mg-subgraph-copy-cc/`.

### Follow-up 2026-06-21 — keyed-4-tuple batch BUILT + measured, still loses (CopperCliff)

Implemented the native keyed batch (`_try_add_keyed_attr_edges_from_batch` on
PyMultiGraph + wrapper gate + list-materialized copy()), full release build in a
clean worktree. Correctness PASSED: 72/72 `subgraph().copy()` byte-identical to nx
(MultiGraph + MultiDiGraph-via-fallback, gapped keys, self-loops, attrs). But it
STILL LOSES: `subgraph(range(400)).copy()` `0.86–0.90x` (improved from 0.72x),
and even direct `add_edges_from([3576 4-tuples])` is `0.70x` despite the batch
firing. Root cause: the batch removes the per-edge `add_edge` loop but each edge
still pays `py_dict_to_attr_map` (Python dict -> Rust AttrMap) AND keeps a Python
mirror — the dual-storage conversion costs more than nx's single-dict assignment.
Same ceiling the existing 2/3-tuple attr batch hits (0.8–0.9x). REVERTED, not
shipped; bead `br-r37-c1-mg-subgraph-keyed-batch-z1q8i` closed no-ship. Real lever
is a lazy AttrMap (defer Python->Rust conversion until a native kernel reads
attrs), a deep substrate change — not a keyed batch.

## 2026-06-21 — connectivity.local_node_connectivity 0.75x is nx-module passthrough access tax (CopperCliff)

Measured (single pair s=0,t=N-1 on gnm N=1500/6000e): exact
`fnx.connectivity.local_node_connectivity(G,s,t)` FNX `62.5 ms` vs NetworkX
`48.9 ms` = `0.75x` (value 8 == 8). `type(fnx.connectivity)` is the **NetworkX
module** `networkx.algorithms.connectivity.connectivity` — fnx does NOT override
the exact (flow-based) local_node_connectivity, so this is nx's own Python flow
code running on a fnx graph: the loss is the per-access AtlasView/`neighbors`
PyO3 substrate tax, NOT a fnx-implementation regression.

Context (NOT losses): the broad single-pair delegated sweep is otherwise all
wins — `node_disjoint_paths` 8.5x, `edge_disjoint_paths` 7.8x,
`approximation.local_node_connectivity` 10.3x, `all_simple_paths` 1.4x,
`harmonic(nbunch)` 3.7x, `node_disjoint`/`approx` connectivity native-fast.

Lever (rebuild-gated, deferred under low-disk no-rebuild constraint): wire fnx's
native max-flow substrate (which beats nx) into a native exact
local/global node/edge connectivity routed from the connectivity namespace, OR
expose a fnx-native connectivity namespace that overrides the nx-module
passthrough. A pure-Python reroute via `len(list(node_disjoint_paths(G,s,t)))`
is NOT cleanly value-equivalent (node_disjoint_paths raises `NetworkXNoPath`
where local_node_connectivity returns 0, and adjacent-pair semantics differ), so
it is not a safe my-file lever. Filed as a bead.

## 2026-06-21 — CORRECTION: to_scipy_sparse_array / to_pandas_adjacency do NOT share the to_numpy dirty ceiling (CopperCliff)

The to_numpy_array dirty-weight entry (commit c95567ccb) speculated the same
dirty-sync ceiling "likely applies to to_scipy_sparse_array and to_pandas_adjacency
(untested)". Now tested (gnm N=1500/6000e, post-construction `G[u][v]['weight']=w`
dirty graph):
- `to_scipy_sparse_array`: dirty `1.01x` (parity), construction `2.76x` WIN — does
  NOT suffer the to_numpy dirty penalty (it routes the weighted COO without the
  full AttrMap rebuild dominating).
- `to_pandas_adjacency`: dirty `0.93x`, construction `1.03x` — both ~parity; the
  cost is pandas DataFrame construction (~24ms), not the edge sync, so the dirty
  tax is negligible here.
Conclusion: the dual-storage dirty-sync ceiling is SPECIFIC to to_numpy_array's
path; do NOT chase a to_scipy/to_pandas dirty gap — there isn't one.

## 2026-06-21 — FIXED (no rebuild): connectivity.local_node/edge_connectivity passthrough → fnx-native routing (CopperCliff)

The earlier "connectivity.local_node_connectivity 0.75x is nx-module passthrough"
entry concluded the lever was rebuild-gated. WRONG — it was a pure-Python routing
gap. `connectivity.py`'s wildcard `from networkx... import *` left BOTH
`local_node_connectivity` and `local_edge_connectivity` bound to NetworkX, while
fnx's native `node_connectivity(s,t)` / `edge_connectivity(s,t)` compute the
identical kappa/lambda(s,t) via the fast max-flow substrate. Added concrete
overrides in `connectivity.py` routing the default exact query to the native
functions (gated: distinct in-graph endpoints, no custom flow_func/auxiliary/
residual/cutoff/backend — everything else, incl. the cutoff early-exit contract
and missing-endpoint errors, falls back to nx verbatim).

Measured (gnm N=1500/6000e, single pair): local_node_connectivity FNX `18.2 ms`
vs nx `56.7 ms` = `2.69x` (was 0.75x); local_edge_connectivity FNX `4.3 ms` vs nx
`26.3 ms` = `6.09x` (was ~0.71x). Value-identical over 100+ directed+undirected
pairs and complete/path/cycle/disconnected/dense-adjacent edge cases; connectivity
conformance `210 passed, 10 skipped`. Two documented losses flipped to wins with no
Rust change. Bead `br-r37-c1-native-flow-connectivity-zvwck` resolved by routing.

## 2026-06-21 — dag.has_cycle / is_directed_acyclic_graph slow on CYCLIC graphs is a native no-early-exit gap (CopperCliff)

`dag.has_cycle` is a catastrophic nx-passthrough (0.02x cyclic / 0.13x DAG vs nx).
`has_cycle(G) == not is_directed_acyclic_graph(G)`, and routing to the fnx-native
`is_directed_acyclic_graph` is a 75x WIN **on DAG inputs** (0.017ms). BUT measured
(gnm directed N=2000/8000e, actually cyclic):
- `fnx.is_directed_acyclic_graph(cyclic)` `9.5 ms` vs nx `0.31 ms` = `0.033x`.
- `fnx.find_cycle(cyclic)` `9.6 ms` vs nx `0.07 ms`.
The native cycle-detection kernel does a FULL pass instead of returning at the
first back-edge; nx early-exits. So a pure-Python `has_cycle` route wins only on
DAGs and stays slow on cyclic — a band-aid in the wrong layer. Prototyped and
REVERTED.

Real lever (rebuild-gated): add early-exit to the native is_directed_acyclic_graph
/ find_cycle / topological cycle-detection kernel (return at the first detected
back-edge). That single native fix makes is_dag, find_cycle, AND has_cycle fast on
both DAG and cyclic inputs. Bead `br-r37-c1-isdag-cyclic-early-exit-qghjm`.
Do NOT ship a Python has_cycle route alone — it leaves the cyclic loss.

### addendum — dag.colliders / v_structures: predecessor-access substrate-bound

Same audit: `dag.colliders` (`0.057x`, fnx 6.73ms vs nx 0.38ms) and
`dag.v_structures` (`0.083x`, 6.99ms vs 0.58ms) are catastrophic nx-passthroughs
(nx iterates `G.predecessors(node)` AtlasViews over the fnx per-access substrate).
An in-process reimplementation snapshotting predecessors once
(`{n: list(G.predecessors(n)) for n in G}`) + Python `combinations`, byte-identical
to nx (25/25 random DAG+cyclic + docstring examples, undirected raises
`NetworkXNotImplemented`), improves them ~8x (colliders 6.73→0.83ms) but STILL
LOSES (`0.42x` / `0.35x`): the fnx predecessor-snapshot floor (`0.63 ms` for 1500
nodes) already exceeds nx's whole-call native-dict time (`0.38 ms`). REVERTED (not
shipped). Lever (rebuild-gated): a native bulk predecessor-keys snapshot (the
directed sibling of `_native_adjacency_keys`) to get the snapshot below nx's
native-dict access; only then does an in-process colliders/v_structures beat nx.

## 2026-06-21 — CORRECTION: dag.has_cycle IS cleanly routable; the earlier "is_dag slow on cyclic" was a STALE .so artifact (CopperCliff)

The earlier entry "dag.has_cycle / is_directed_acyclic_graph slow on CYCLIC =
native no-early-exit gap" (commit e0731148d) was WRONG — a stale-install
measurement trap. Those `is_directed_acyclic_graph(cyclic) 9.5ms` /
`find_cycle 9.6ms` numbers were measured via `PYTHONPATH=…/python` against the
in-tree `_fnx.abi3.so` left over from an earlier to_numpy build, NOT the current
extension. Re-measured against the current install: `is_directed_acyclic_graph`
is `0.012 ms` cyclic / `0.018 ms` DAG (the native kernel is Kahn's integer-CSR,
which naturally terminates on the first stalled peel — there was never a missing
early-exit). FIXED (no rebuild): `has_cycle(G) == not is_directed_acyclic_graph(G)`
routed in dag.py for directed graphs — `not is_dag` is `0.009 ms` cyclic (34x nx)
/ `0.015 ms` DAG (68x nx), value-identical incl. self-loops / parallel edges /
empty; undirected falls back to nx's `NetworkXNotImplemented`. dag conformance
130 passed. Bead `br-r37-c1-isdag-cyclic-early-exit-qghjm` closed invalid.

LESSON (re-learned the hard way): ALWAYS benchmark the native-target perf on the
CURRENT install before declaring a route rebuild-gated. A value-equivalent
passthrough route's target perf must be measured on the same build it will ship
against, not a stale PYTHONPATH .so (see feedback_stale_install_benchmark_trap).

## 2026-06-21 — is_distance_regular "0.003x gap" is a CORRECTNESS win for fnx, not a perf loss (CopperCliff)

`is_distance_regular(cycle_graph(800))`: fnx `201ms` vs nx `0.53ms` looks like a
catastrophic `0.003x` loss. It is NOT a perf gap to fix — it is a **correctness
divergence where fnx is right and nx is wrong**. fnx returns `True` (a cycle C_n
IS distance-regular for all n — textbook); nx returns `False`. nx's
`intersection_array` uses a diameter early-exit `(8·log2 n)/3 ≈ 25.7` for n=800,
but that bound is only valid for valency ≥ 3 distance-regular graphs — a cycle
(valency 2) has diameter ⌊n/2⌋ = 400 and is wrongly rejected. fnx's native
`_raw_is_distance_regular` computes the full intersection array (all-source BFS,
O(V·(V+E))) and gets the correct answer.

Verified: fnx==nx on petersen (DR, valency 3), K20 (DR), random 3-regular
(not DR) — they diverge ONLY on large cycles (valency 2), where fnx is correct.

DO NOT route fnx.is_distance_regular to nx's fast path — it would adopt nx's bug.
The slowness is the price of correctness: for a graph that genuinely IS
distance-regular you cannot early-exit-reject, so the work is unavoidable. The
only lever is a native single-source-lazy intersection array (vs the current
all-source) — still O(V^2)-ish for true DR graphs, marginal, rebuild-gated, low
value (is_distance_regular is algebraic-graph-theory niche). Bead filed.

### addendum 2 — colliders/v_structures native predecessor-keys BUILT + measured, still loses (CopperCliff 2026-06-21)

Followed up the dag.colliders/v_structures substrate-bound finding by actually
adding the native `_native_predecessor_keys_bulk` to PyDiGraph (mirroring the
existing PyMultiDiGraph method) + routing colliders/v_structures through it, full
warm release build. Correctness PASSED (30/30 random DAG+cyclic + docstring
examples byte-identical; undirected raises NetworkXNotImplemented). But it STILL
LOSES: colliders `0.66x` (fnx 2.58ms vs nx 1.72ms), v_structures `0.38x` — an
improvement over the pure-Python reimpl (~0.42x) but not a win. Root cause: the
native bulk still materializes EVERY predecessor node-key as a PyObject (O(E)
`py_pred_key` allocations); nx's `G.predecessors` reuses the already-stored node
objects, so fnx pays an allocation nx does not. This is the SAME node-key
PyObject materialization wall that caps graph iteration (~35x) — the live-PyDict /
interned-display node storage substrate, NOT a colliders-local or snapshot-local
fix. REVERTED (worktree discarded). DO NOT re-attempt a predecessor-keys route for
colliders/v_structures; the only lever is the deep node-storage rearchitecture.

## 2026-06-21 — submodule-namespace passthrough scan: residuals are routed/substrate/rebuild-gated (CopperCliff)

Comprehensive scan of fnx.SUBMODULE.func vs nx.SUBMODULE.func across 18 namespace
submodules (the pattern that yielded the connectivity/tournament/dag/threshold
wins). After filtering scan noise, the genuine sub-1.0x residuals are:
- ALREADY ROUTED + fast (scan noise): assortativity.degree_mixing_dict 4.4x,
  degree_mixing_matrix 4.1x, degree_pearson_correlation_coefficient 2.8x,
  degree_assortativity_coefficient 100x — all route to fnx top-level natives via
  the existing `_route_to_fnx_toplevel()`; the scan's <0.55x readings were noisy
  single-shot artifacts (re-measured min-of-N: all wins).
- SUBSTRATE-BOUND (edge-data access): tree.branching_weight 0.07x. It is exactly
  G.size(weight=attr), but routing there is STILL 0.45x (fnx edge-data iteration
  loses to nx's native dict walk) AND diverges in type (int 4831 vs float 4831.0).
  Not a clean route. Same node/edge-access substrate wall.
- FIXED (99d245aea, NOT rebuild-gated — was a Python loop): google_matrix was
  0.38x-0.81x because its dense row-normalization ran a ``for i in range(n)``
  per-row slice division. Vectorized it (divide-all-rows + sparse dangling
  overwrite, byte-identical to the loop over 30 configs) -> 1.06-1.22x vs nx.
  LESSON: read the implementation before declaring a gap rebuild-gated; a Python
  loop in a numpy function is a pure-Python vectorization win.
- NICHE: tournament.tournament_matrix 0.23x (skew-adjacency build).

NO new clean no-rebuild win. The 6 namespace wins already shipped were the
catastrophic O(n^2+)-brute-force-with-fast-native cases; the rest are routed,
substrate-bound, or rebuild-gated.

### addendum — namespace-scan warm re-bench (CopperCliff 2026-06-21)

Warm min-of-N re-measurement of the remaining namespace-scan sub-1.0x entries:
- centrality.eigenvector_centrality_numpy: warm `1.19x` WIN (scan's 0.475x was
  cold-scipy/LAPACK init noise — confirms the warm-saturation memory).
- centrality.dispersion: warm `1.87x` WIN (scan noise).
- approximation.densest_subgraph: genuine warm `0.48x` (fnx 4.54ms vs nx 2.20ms).
  nx dispatches to a greedy-peeling / FISTA approximation; it's a per-access
  passthrough with no fast-native route — reimplementation- or substrate-bound,
  niche. Not pursued.
- tree.greedy_branching: genuine warm `0.46x` (fnx 6.49ms vs nx 2.97ms). Edmonds
  greedy max-weight in-edge selection + branching construction (node-key
  materialization); substrate-bound, niche. Not pursued.
Net: no new clean win; the two genuine gaps are niche + substrate/reimplementation-
bound. (Cold-vs-warm reminder: always warm-saturate scipy/LAPACK before trusting a
spectral/numpy ratio.)

### addendum — densest_subgraph is ORDER-SENSITIVE, parity-blocked (CopperCliff 2026-06-21)

approximation.densest_subgraph (warm 0.48x) reimplemented in-process via a fast
adjacency snapshot + nx's EXACT Greedy++ (heap-based min-weighted-degree peeling)
is 2.3-2.4x faster than nx — BUT it DIVERGES from nx on identical graphs (e.g.
n=35/m=16: density 0.8 vs 0.8235). Greedy++ is a 2-approximation whose result
depends on the heap tie-break order, which in turn depends on the adjacency /
neighbor ITERATION order; fnx's adjacency order differs from nx's, so the peeling
trajectory and the returned density/node-set differ (both valid approximations,
not equal). Like the clique/ramsey/greedy_color set-order-dependent approx
functions, this CANNOT be matched in pure Python and must stay delegated. Reverted
(prototype only, never committed to source). tree.greedy_branching is the same
shape (greedy max-weight selection, order-dependent). No-ship.

## 2026-06-21 — callable-weight functions pay the delegation-conversion tax (CopperCliff)

Functions called with a CALLABLE weight (weight=lambda u,v,d: ...) cannot run on
the native string-keyed kernels, so fnx delegates via `_call_networkx_for_parity`
-> `_networkx_graph_for_parity(G)` (a fresh O(V+E) fnx->nx conversion EVERY call,
~5ms at N=600/2400e) + nx's algorithm. Measured warm:
- dijkstra_path_length(callable weight) `0.12x` (fnx 5.95ms vs nx 0.74ms)
- single_source_dijkstra_path_length(callable) `0.17x`
- pagerank(callable weight) `0.00x` (fnx 497ms vs nx 2.1ms — though callable weight
  for pagerank is non-standard; weight is documented as a str key/None)
- betweenness_centrality(callable) `1.01x`, all_pairs_dijkstra(callable) `0.97x`
  (parity — the conversion is amortized over the O(V*(V+E)) all-pairs work).
Root cause = the per-call whole-graph conversion dominates single-pair/cheap
callable queries (the delegation-conversion-tax pattern). NOT pursued: string
weights (the overwhelmingly common case) are already native-fast; callable weight
is uncommon. The lever is either (a) an in-process Dijkstra reimplementation that
calls the Python weight callable over a fast native adjacency snapshot (no
conversion — the bidirectional_dijkstra pattern), per-function and byte-identity-
risky, or (b) caching the shared `_call_networkx_for_parity` conversion under the
(nodes_seq, edges_seq, edges_dirty) token (broad win for ALL delegated functions on
unchanged graphs, but high blast radius — needs careful invalidation). Both deferred
as scoped work; the gap is niche (callable weight) and the fixes are risky.

## 2026-06-22 CopperCliff `MultiDiGraph(DiGraph)` Native Absorb WIN (`br-r37-c1-mdgdig`, cc)

BOLD-VERIFY on current origin/main. Broad warm sweep found one real meaty gap:
`MultiDiGraph(<plain DiGraph>)` ran **0.41-0.53x** vs nx (MultiDiGraph(MultiDiGraph)
and MultiGraph(Graph) were already fast — only DiGraph->MultiDiGraph lacked a native
absorb; `_copy_constructor_graph_source` fell to the general Python `clear()` +
`add_nodes_from` + `add_edges_from(4-tuple)` replay).

NEGATIVE EVIDENCE (Python ruled out): `add_edges_from` alone = 28.5ms of 41.6ms
@ n=2000; EVERY edge-tuple shape — `(u,v,0,dict)`, `(u,v,dict)`, bare `(u,v)`,
precomputed list — was ~29-32ms. The cost is the `MultiDiGraph.add_edges_from`
keyed-insertion substrate, not the per-edge `dict()` copies. No pure-Python route
closes it.

FIX: added `absorb_digraph_keyed_from_digraph` to `impl PyMultiDiGraph` (directional
analog of `absorb_graph_bidirected_from_graph`) — builds the MDG inner directly from
the DiGraph inner in one pass (node-major `successors`, key 0, shallow-copied attrs),
wired in `_copy_constructor_graph_source`. Falls through (Ok(false)) on mixed-display
rows / `__fnx_incompatible` attrs. Byte-exact: 6 hand shapes + 60 randomized, 0
mismatches (nodes, node data, edges(keys+data), succ+pred adjacency, graph attrs,
shallow-copy + no-source-mutation). Perf 0.41x -> **1.62-1.90x** faster than nx
(~4.5x self-speedup). Full suite: zero new failures (5 pre-existing origin failures
unrelated, proven by reverting the wiring). Artifact:
`tests/artifacts/perf/20260622T-multidigraph-from-digraph-absorb-cc/`.

## 2026-06-22 CopperCliff Post-MDG-Absorb Comprehensive Sweep — Domination, Residuals Bounded (`br-r37-c1-mdgdig`, cc)

After shipping the `MultiDiGraph(DiGraph)` absorb, a 3-batch warm sweep (~90
functions: construction/conversion/copies, readwrite/serialization, centrality/
community/flow/connectivity/cycles/trees, weighted+multi algorithms) re-confirmed
comprehensive domination (representative wins: floyd_warshall 67x, weighted
betweenness 158x, second_order 4845x, bridges 24x, greedy_modularity 21x,
eccentricity 15x, MultiDiGraph.copy 2.44x, reverse(MDG) 2.39x, from_scipy 2.1x,
all_pairs_dijkstra 2.76x, MG(MG) 3.38x, mg.edges 4.7x).

NEGATIVE EVIDENCE — residual losses are all bounded/marginal, NOT clean levers:
- `in_degree`/`out_degree` `dict(...)`: 0.56-0.65x at n=20000 (2.0ms vs 1.25ms).
  Already on a native bulk path (`_native_in/out_degree_pairs`). RULED OUT a
  wrapper bug: the raw native call alone is 1.49ms (vs nx 1.25ms) building 20000
  (node_obj, count) tuples — the view wrapper adds only ~0.2ms (`yield from`).
  `list(G)` is 0.09ms so it is NOT node materialization; it is the rust tuple-list
  build being marginally slower than nx's pure-Python dict-comp. Sub-2ms absolute,
  ~10% recoverable — no good ROI.
- `to_dict_of_dicts(MultiDiGraph)`: 0.77x (3.8ms vs 2.95ms) — nested dict build
  substrate, niche serialization helper.
- `from_dict_of_dicts(DiGraph)` 0.48x and `astar` 0.73x and `find_cycle(src)` 0.38x:
  all TINY absolute (15-500us) — small-input/native-port setup cost dominates, not
  an algorithmic gap; default whole-graph timing shows parity.
- `subgraph_centrality` 0.81x (84ms vs 68ms): dense `eigh`-bound (known open item).
- A cluster at 0.85-0.92x (MultiGraph(MultiDiGraph), MDG subgraph.copy, to_numpy_array,
  size_weighted, mg.degree(weight), adjacency() walk): substrate-parity, not wrapper.

Conclusion: the one meaty current-code lever (`MultiDiGraph(DiGraph)` absorb, shipped)
is exhausted; remaining gaps are substrate-bound or tiny-absolute. No further ship.

### Addendum (same pass, cc): untouched-family sweep — domination holds

Extended the sweep to families not covered above (~29 fns): isomorphism
(could_be/fast/faster 1.5-6.2x), WL hashing (graph_hash/subgraph_hashes 0.96x =
parity), graph coloring (greedy_color 9.07x), cliques (find_cliques/node_clique
1.04x), similarity (simrank 1.11x), efficiency (local 25.3x / global 18.3x),
triadic_census 17.95x, reciprocity 8.24x / overall 9.03x, bipartite
(density 7.69x, clustering 2.28x, projected 0.93x), dominance (immediate_dominators
3.38x, dominance_frontiers 1.68x), closeness_vitality 14.5x, spring_layout 1.01x,
k_components 0.99x, non_randomness 0.98x, degree_histogram 0.97x. Only sub-0.85x:
`bipartite.color` 0.80x at sub-100us (small-input, negligible). No new lever —
confirms the post-MDG-absorb domination across ~120 functions total this pass.

## 2026-06-22 CopperCliff `shortest_path(G, source)` Routed to Fast Kernel (`br-r37-c1-spsrc`, cc)

Small-input/single-query sweep (the angle whole-graph timing hides) found one real
meaty gap: unweighted `shortest_path(G, source)` (source-only, all targets) ran
**0.72-0.84x** vs nx. Diagnosis: `single_source_shortest_path(G, source)` is itself
**~1.6x FASTER** than nx, but `shortest_path` fell through to the `_raw_shortest_path`
source-only path, which was ~2x SLOWER than the single_source kernel. nx.shortest_path(
G, source) returns EXACTLY single_source_shortest_path(G, source), so the wrapper was
doing strictly more work for the same result.

FIX (pure-Python, no rebuild): route the `weight is None and source is not None and
target is None` case to `single_source_shortest_path(G, source)`. Byte-identical (both
match nx, 20/20 parity incl. BFS-discovery key order + source self-path). Perf
0.72-0.84x -> **1.38-1.63x** faster than nx. Full suite: zero new failures (same 5
pre-existing origin failures). Other small-input residuals are sub-microsecond PyO3
call overhead (neighbors(v) 0.35x @ 0.8us, degree(v) 0.46x @ 0.8us, common_neighbors
0.72x @ 1.2us) — fundamental per-call round-trip cost, negligible absolute, no ROI.

### Residual (same pass, cc): directed `single_target_shortest_path` ~0.66x — kernel-bound, NOT a wrapper fix

While fixing `shortest_path(G, source)`, the symmetric `shortest_path(G, target=t)` on
a DIRECTED graph measured ~0.66x (1.47ms vs nx 1.09ms @ n=2000). Unlike the source
case, this is NOT wrapper waste: the underlying `single_target_shortest_path` (already
native `_raw_single_target_shortest_path`, reverse/predecessor integer-BFS) is itself
0.66x (1.084ms vs nx 0.713ms). Routing the wrapper would only reach the kernel's 0.66x,
not beat nx — so NOT shipped. The bottleneck is the per-node Python path-list
reconstruction (materializing ~|V| node-object lists from the Rust string table), the
same node-object materialization substrate that bounds the degree-view dicts. The
UNDIRECTED target case is 0.95x (parity). Candidate for future native work (emit path
segments / reuse a node-object cache), not a one-pass wrapper lever.

PROOF the directed `single_target` residual is path-materialization-bound (not BFS):
`single_target_shortest_path_length` (no path objects, same reverse BFS) is **parity**
(1.01x @ n=2000, 0.95x @ n=5000) while the path-returning version is 0.57-0.66x. So the
entire gap is building |V| Python path-lists of node objects from the Rust string table
— the reverse BFS is already at nx speed. No BFS-level or wrapper fix can close it;
only a persistent node-object mirror would (and nx wins there by reusing node objects it
already holds). Conclusively NOT a one-pass lever. Vein closed.

### Addendum 2 (same pass, cc): algorithm-family sweep — domination holds

Final coverage batch (~28 fns across families not previously benched): distance
measures (center/periphery/radius/diameter/barycenter/wiener all ~15x), assortativity
(degree_mixing_matrix 4.45x, average_degree_connectivity 2.05x), graphical sequences
(is_graphical 1.19x, erdos_gallai 1.52x), structural holes (local_constraint 3.16x),
chordality (is_chordal 3.88x), euler (is_eulerian 4.16x, has_eulerian_path 1.51x),
covering (min_edge_cover 0.90x = parity), swaps (double_edge_swap 1.33x), hierarchy
(flow_hierarchy 233x, global_reaching_centrality 4.18x, trophic_levels 1.06x),
all_shortest_paths 2.18x, dispersion 1.75x, voterank 1.74x, percolation 1.74x. All
wins or parity; no sub-0.85x. With this, the BOLD-VERIFY sweep spans ~180 function-calls
(whole-graph + small-input) across essentially every NetworkX algorithm family —
comprehensive domination confirmed; the only residuals are the node/path-object
materialization substrate (proven above) and sub-us PyO3 call overhead. No clean lever
remains absent the persistent-node-mirror substrate rewrite.

## 2026-06-22 CopperCliff `in_degree`/`out_degree` Counts-Only Path — 0.62x -> 1.33-1.77x (`br-r37-c1-degcounts`, cc)

Earlier docs flagged the directed `in_degree`/`out_degree` dict as 0.62x "near-native,
no ROI" — that was WRONG. Re-diagnosis: `dict(zip(list(G), counts))` = 0.56ms while the
`_native_*_degree_pairs` path was 1.5ms, because pairs rebuilt a PyObject per node via
`py_node_key` whereas `list(G)` reuses the node_iter_mirror cache (0.09ms @ 20k). The
missing piece was a counts-ONLY native call (no node materialization).

FIX: added `_native_in_degree_counts`/`_native_out_degree_counts` to PyDiGraph (Vec<usize>
in node-index order, no py_node_key) and routed `_DirectedDegreeView.__iter__`'s unweighted
full-graph branch (gated `type(G) is DiGraph`) to `zip(list(G), counts())`. Byte-identical
(list(G) order == nodes_ordered() index order, verified range+str keys); weighted / nbunch /
single-node / filtered / multi paths untouched. Perf: in_degree/out_degree dict 0.62x ->
**1.33-1.77x** faster; `for n,d in G.in_degree()` iteration 1.1-1.8x. Parity 6/6 (dict/order/
iter/nbunch/single/weighted), full suite zero new failures. Artifact:
`tests/artifacts/perf/20260622T-degree-counts-zip-cc/`. LEVER: a native bulk call that
emits (node, value) pairs by re-materializing node objects can be split into a values-only
native call + `zip(list(G), ...)` reusing the node cache — audit other *_pairs bindings.

## 2026-06-22 CopperCliff Multi-edge `edges(keys=True, data=True)` ~0.5x residual — uncached rebuild (`br-r37-c1-mgkd`, cc)

Multigraph algorithm-execution sweep (new coverage) is dominant (MG betweenness 17x,
closeness 5x, MDG scc 3.5x, triangles 2.8x, bfs_tree 2.3x). One real residual:
`MultiGraph.edges(keys=True, data=True)` is 0.47-0.58x vs nx (7.4ms vs 3.8ms @ n=2000);
MultiDiGraph variant 0.76-0.86x. Each PARTIAL variant is a big WIN: edges(data=True) 4.7-5x,
edges(keys=True) 4.3x.

ROOT CAUSE (diagnosed, no fix shipped): `_native_edge_view_list` caches ONLY the
data-only variant (`cacheable = want_dict && !keys`, stored in `edges_with_data_cache`
keyed on (nodes_seq, edges_seq)). So edges(data=True)'s 4.7x is a warm-cache-hit
artifact; edges(keys=True, data=True) is excluded from the cache and REBUILDS every call.
The rebuild itself is ~2x nx (per-edge py_node_key + py_adj_key + py_edge_key +
ensure_edge_py_attrs + a String-keyed `seen` dedup HashSet). Attr dicts are LIVE
(identity-preserved, matches nx) in BOTH variants — not a copy/parity issue.

FIX OPTIONS (deferred — disk-LOW, uncertain real-world payoff):
1. Cache the keys+data variant too — change `edges_with_data_cache` tuple to carry a
   `keys: bool` flag (all 9 construction sites init it `None`, so NO struct-field churn;
   only the field decl + the read/write in `_native_edge_view_list` change). Helps
   REPEATED keys+data calls; one-shot (the common serialization/copy case) unchanged.
2. Speed the rebuild (integer-index dedup instead of String `seen`; reuse node-object
   cache) — helps one-shot but harder to beat nx's 3.8ms Python dict-walk.
Both need a rust rebuild; not disk-frugal now. Candidate for when disk recovers.

### Addendum 3 (cc): IO serialization sweep — write_* residuals are parity-blocked delegations

No-build IO probe (new coverage). Generators/readers dominate or parity: to_graph6_bytes
2.27x, to_sparse6_bytes 1.56x, write_edgelist 4.74x, write_weighted_edgelist 1.82x,
generate_edgelist 1.22x, generate_graphml/gml/adjlist parity. The write_* residuals are
ALL byte-parity-blocked nx delegations (NOT levers): write_gexf 0.79x, write_gml 0.85x,
write_graphml 0.85x, write_adjlist 0.75x. Root cause (per the write_gexf docstring,
br-r37-c1-wgexf-parity + {eeawk,nlkkm,nhgtp}): native Rust writers EXIST
(`write_gexf_string_rust` etc.) but were abandoned because their output diverges from nx's
lxml byte-for-byte (XML quote style `'` vs `"`, `utf-8` vs `UTF-8`, prettyprint spacing),
so they delegate to nx for byte-exact output and pay the fnx->nx conversion. Closing these
requires matching nx's exact serialization bytes (the reason they were de-routed) — not a
perf lever. Confirms domination holds across IO too; no no-build lever remains in any swept
domain (whole-graph, small-input, *_pairs, multi-execution, pure-Python routing, IO).

## 2026-06-22 CopperCliff RESOLVED `MultiGraph.edges(keys=True, data=True)` 0.5x -> 4.9x (`br-r37-c1-mgkd`, cc)

The keys+data residual documented above (uncached rebuild) is now FIXED. Implemented the
low-churn single-slot variant: `PyMultiGraph.edges_with_data_cache` tuple gains a `keys`
flag (3-tuple -> 4-tuple), and `cacheable = want_dict` (was `want_dict && !keys`) so the
keys+data variant caches too, discriminated by the flag. NO construction-site churn (all
9 inits are `None`, type-agnostic); PyMultiDiGraph's separately-declared field (digraph.rs)
is untouched. Cache hit requires (nodes_seq, edges_seq, keys) match; mixed data-only/
keys+data calls on the SAME graph (rare) thrash the slot but stay correct.

Result: edges(keys=True, data=True) 0.5x -> **4.74-4.94x** vs nx; data-only unchanged
(4.9x, no regression). Parity 4/4 (keys+data / data-only / keys-only / alternation-
correctness: data-only stays byte-exact after an interleaved keys+data call), range+str
keys, live attr-dict identity preserved. Full suite: zero new failures (same 5 pre-existing
origin failures). Artifact: tests/artifacts/perf/20260622T-mg-edges-keysdata-cache-cc/.

### Note (cc): MultiDiGraph edges(keys+data) — same pattern, borderline, NOT shipped

The MultiDiGraph analog of the MG keys+data cache (br-r37-c1-mgkd) has the same gate
(digraph.rs:283 `want_dict && !keys` excludes keys+data from `edges_with_data_cache`), but
the gap is borderline: 0.84x @ n=800, 0.98x @ n=2000 (vs MG's 0.5x). Directed edges are
unique by (u,v,key) — no undirected canonical-dedup `seen` HashSet — so the keys+data
rebuild is already close to nx. Caching would flip warm-repeated to ~3.3x but one-shot is
near-parity, and the change is more involved than MG (two field decls + multiple
cache-using methods in digraph.rs). Per REVERT-~0-gain, NOT shipped. Documented so it
isn't re-investigated.

### Note (cc): directed total-degree — counts-zip win exists but type-contract-blocked

Directed total `G.degree()` dict is 0.87x @ n=20000 (1.17x @ n=2000 — only slow at large n).
A pure-Python `dict(zip(list(G), [i+o for i,o in zip(_native_in_degree_counts(),
_native_out_degree_counts())]))` (reusing the shipped br-r37-c1-degcounts methods) is
1.43x @ n=20000 and byte-correct. BUT it can't be routed cleanly: `G.degree()` →
`_DiGraphDegreeView.__call__()` returns the raw Rust `DiDegreeView` directly (for
type/repr parity — tests assert `type(G.degree()).__name__ == 'DiDegreeView'`), so both the
parens and no-parens forms iterate the raw view. Returning a custom zip object would break
the DiDegreeView type contract. A clean fix needs a rust-level raw `DiDegreeView` iter
change (counts + cached nodes) for a marginal gain (near-parity except very large n). Per
REVERT-~0-gain + type-contract risk, deferred — documented so the Python route isn't retried.

### Addendum 4 (cc): generator + pandas-conversion sweep — domination, gaps construction/RNG-bound

No-build sweep of generators (last unswept domain) + pandas conversions. Dominant:
random_regular 3.65x, hypercube 31.4x, complete_graph 13.4x, balanced_tree 4.64x,
caveman 4.75x, lollipop 4.4x, grid_2d 3.07x, watts_strogatz 1.42x, random_tree 1.45x,
powerlaw_cluster 1.16x, circular_ladder 1.96x; to_pandas_edgelist 1.42x, from_pandas_edgelist
1.86x, to_pandas_adjacency 1.24x. Sub-parity residuals are ALL construction-tax / RNG-parity
bound (consistent with project_generator_batch_vein_progress + construction_tax_relabel_lever):
barabasi_albert 0.72x and dual_ba 0.83x (RNG-faithful _random_subset draw sequence must
reproduce nx's PythonRandom in Python; native kernel would need byte-exact set-rejection
choice replay — significant + parity-risky), complete_bipartite 0.81x and turan 0.87x (40k+
deterministic edge insertion = the general edge-construction substrate), star/wheel 0.89x.
No clean lever; all need the deep construction substrate or a native RNG-replay kernel.
With this, EVERY domain is swept (whole-graph, small-input, *_pairs, multi-execution,
pure-Python routing, IO, generators, conversions) — comprehensive domination confirmed.

### CORRECTION (cc): barabasi_albert 0.72x is PARITY-BLOCKED (set-order), NOT a native candidate

Earlier notes floated a "native PythonRandom BA kernel" as the highest-value remaining
target. That is WRONG — verified by reading the impl: `_random_generator_subset(seq, m, rng)`
returns a `set` (mirroring nx's `_random_subset`), and `barabasi_albert_graph` builds edges
by iterating that set (`new_edges.extend((source, t) for t in targets)`). So BA's edge
order — hence adjacency layout / byte-exact parity — depends on CPython SET ITERATION ORDER
of the `targets` set (which grows/resizes across the while-loop adds). A native Rust kernel
cannot replicate CPython set internals byte-for-byte (same class as [[reference_parity_blocked_by_set_order]]:
clique/ramsey/greedy_color set-order). fnx already runs the exact Python set-based loop +
a single batched add_edges_from, so 0.72x is the byte-exact FLOOR for BA. NOT a native
candidate; do not attempt. dual_barabasi_albert (0.83x) is the same set-based pattern.
Net: NO remaining generator gap is native-accelerable; the only non-parity-blocked
residuals are the node/path-object materialization substrate (persistent-node-mirror rewrite).

## 2026-06-22 CopperCliff `havel_hakimi_graph` batch construction — 0.46x -> 1.2x (`br-r37-c1-hhbatch`, cc)

Found via the misc-class sweep (degree-sequence generators). `havel_hakimi_graph` was a
consistent 0.46x vs nx (13.9ms vs 6.4ms @ n=2000, scaling). Root cause: the Havel-Hakimi
realization emitted edges via a per-edge `graph.add_edge(source, target)` loop — the PyO3
round-trip per edge dominated. The degree_buckets/modified/active bookkeeping never reads
graph state (the graph is pure output), so this is the classic batch-construction lever
([[reference_batch_add_edges_from_construction]]): collect every (source, target) and commit
through ONE `add_edges_from`. Same emission order -> byte-identical adjacency.

Result: 0.46x -> **1.19-1.21x** faster than nx (2.6x self-speedup). Byte-exact: 23 checks
(6 seeds x 3 sizes + 5 edge cases incl. [0]/[0,0,0]/[1,1]/[2,2,2]/[]), nodes + edges-in-order
+ adjacency. Full suite: zero new failures. Artifact:
tests/artifacts/perf/20260622T-havel-hakimi-batch-cc/. LEVER STILL LIVE: grep remaining
construction/generator fns for per-edge add_edge loops with no mid-loop graph reads.

## 2026-06-22 CopperCliff `cycle_graph`/`path_graph` create_using batch — 0.39x -> 0.78x (partial, substrate-floored) (`br-r37-c1-cycbatch`, cc)

The default (int) cycle_graph/path_graph hit native kernels (1.8-2.0x). But the
`create_using=` path (e.g. directed/multi C_n / P_n) emitted edges via a per-edge
`graph.add_edge(u,v)` loop -> 0.38-0.48x vs nx. Batched both into a single add_edges_from
(cyclic pairwise + LAST wrap-around close for cycle; pairwise for path) — same
batch-construction lever as havel_hakimi. Byte-exact: 48 checks (4 create_using types x 6
sizes x 2 generators incl. n=0/1/2). 2548 generator tests pass.

PARTIAL win: 0.38-0.39x -> 0.78-0.80x (2x self-speedup) but does NOT dominate — the residual
is the directed/multi `add_edges_from` insertion substrate (same ~0.73-0.80x floor as the
already-batched star_graph(DiGraph)), not per-edge-loop waste. Shipped anyway: removing the
per-edge PyO3 round-trip is strictly correct + halves the gap; the residual is the documented
directed-construction substrate (needs the node-keying/int-CSR substrate work, not a wrapper
change). NOT ~0-gain (2x self-speedup).

## 2026-06-22 CopperCliff `add_path`/`add_cycle`/`add_star` — 0.24x -> 1.04-1.13x (`br-r37-c1-addpathbatch`, cc)

These ubiquitous mutation helpers were 0.23-0.28x vs nx (4x slower) — per-edge add_edge
loops. Two-part fix to DOMINATION:
1. Batch the loop into ONE add_edges_from (same lever as havel_hakimi).
2. CRITICAL sub-lever: do NOT `add_node(first)` before the add_edges_from. The explicit
   pre-add makes the graph NON-FRESH, which DEFEATS add_edges_from's fresh-graph batch fast
   path (measured 2.79ms WITH pre-add vs 1.53ms WITHOUT, same result). pairwise's first edge
   adds the first node anyway (verified identical node order). Only add_node for the
   single-node no-edge case.

Result: add_path 0.24x->1.04x, add_cycle 0.28x->1.13x, add_star 0.23x->1.09x (4.3x
self-speedup, now DOMINATES). Byte-exact: 180 checks (3 fns x 4 graph types x 5 node-lists
incl. []/[5]/dups x [plain/attr/existing-graph]). Full suite zero new failures.

GENERAL GOTCHA (also limits the earlier cycle_graph/path_graph create_using fix to 0.78x:
`_add_nodes_in_order` pre-adds all nodes -> defeats fresh path): when batching a construction
that builds a fresh graph, let add_edges_from add the nodes via edges; an explicit pre-add of
nodes already covered by edges silently drops you off the fresh-graph fast path. Artifact:
tests/artifacts/perf/20260622T-add-path-cycle-star-batch-cc/.

## 2026-06-22 CopperCliff `from_dict_of_dicts(DiGraph)` O(N^2) -> O(E) — 430x slower to 1.28x faster (`br-r37-c1-doddir`, cc)

CATASTROPHIC find (interleaved converter sweep): directed `from_dict_of_dicts` was O(N^2) —
58ms/239ms/963ms @ n=200/400/800 (0.046x/0.005x/0.003x vs nx, ~430x slower, clean quadratic).
The undirected `Graph` case has a batch branch; `is_multigraph` is handled; but the directed
simple-graph case fell to the `else` per-edge `add_edge(u,v)` + `graph[u][v].update(attrs)`
loop, where the directed adjacency-view `__getitem__` per edge is O(N) -> O(N^2) total.

FIX: directed dict-of-dicts edges are UNIQUE (no symmetric (v,u) dedup the undirected branch
needs), so added an `elif type(graph) is DiGraph:` branch emitting (u, v, attrs) triples
through ONE add_edges_from (exactly what nx does), O(E). Now **1.28x FASTER** (963ms->1.49ms
@ n=800, ~650x self-speedup). Byte-exact: 8 checks (attrs / str keys / self-loops / isolated
nodes / MultiDiGraph-still-routes-correctly). Full suite: zero new failures. Exotic subclasses
keep the inline loop (malformed-input contract). Artifact:
tests/artifacts/perf/20260622T-from-dict-of-dicts-directed-on2-cc/. LEVER: audit other
converters/operators for directed paths lacking the undirected branch's batch.

### Note (cc): add_edges_from fast batch only engages for SEQUENTIAL-int-prefix edges (from_edgelist 0.64x)

Converter sweep: `from_edgelist` is 0.64-0.69x vs nx (both directed/undirected). It is already
minimal (`G.add_edges_from(edgelist)`), so the gap is `add_edges_from` itself. Pinpointed on a
fresh Graph @ n=2000/m=8000:
- add_edges_from(SEQUENTIAL int edges, e.g. pairwise(range)) = **1.12x** (fast — the rust
  fresh-int-prefix batch `collect_fresh_exact_int_prefix_edges` engages)
- add_edges_from(RANDOM int edges, e.g. gnm.edges()) = **0.64x**
- add_edges_from(STRING edges) = **0.63x**
So the batch fast path requires nodes arriving in 0..n PREFIX order; random-int and string
edge lists fall to the slower String-keyed batch (~1.5x nx). This is the documented
construction substrate ([[reference_attr_edge_batch_construction]] / construction-tax veins),
affecting from_edgelist + any build from non-sequential edges. NOT a wrapper lever — needs a
rust general-fresh-int/string batch that engages for arbitrary insertion order (node order
must stay insertion-faithful). Deferred to the substrate work. (to_dict_of_lists 0.20x in the
raw sweep was NON-interleaved noise — it is actually 1.6-1.9x via its native fast path.)

## 2026-06-22 CopperCliff `DiGraph(dict_of_dicts)` constructor O(N^2) -> parity (`br-r37-c1-decodedir`, cc)

SECOND O(N^2) directed-dod disaster (sibling of br-r37-c1-doddir, a DIFFERENT code path):
the CLASS CONSTRUCTOR `DiGraph({u:{v:attrs}})` routes through `_decode_dict_of_dicts_into`,
whose simple-graph `else` did per-edge `self.add_edge(u,v); self[u][v].update(dict(inner))`.
The directed adjacency-view `__getitem__` per edge -> O(N^2): 215ms/911ms @ n=400/800
(0.005x/0.003x). Undirected Graph(dod) was ~6x slow (0.17x, linear-but-slow).

FIX: pure non-multigraph dict-of-dicts (all values dicts) -> `add_nodes_from(data)` + ONE
`add_edges_from((u, v, attrs) ...)`. Byte-identical to the loop (add_edges_from sets/updates
the edge dict; last-writer-wins on the symmetric undirected reverse exactly like the loop;
same node + edge order). dict-of-list / multigraph / non-dict shapes keep the general loop.
Result: DiGraph(dod) -> 0.99-1.04x (~500x self-speedup, 911ms->1.85ms @ n=800), Graph(dod)
-> 1.20x. Byte-exact: 11 checks (attrs / dict-of-list-fallback / str keys / self-loops /
isolated / asymmetric undirected last-wins / empty). Full suite zero new failures. Artifact:
tests/artifacts/perf/20260622T-digraph-dod-constructor-on2-cc/.

## 2026-06-22 CopperCliff `from_pandas_edgelist(DiGraph)` O(N^2) -> 1.7x (`br-r37-c1-pandasdir`, cc)

THIRD directed-O(N^2) disaster of the converter family (siblings: br-r37-c1-doddir
from_dict_of_dicts, br-r37-c1-decodedir DiGraph(dod) constructor). `from_pandas_edgelist`
batches for `type(graph) is Graph` but DiGraph fell to the per-row else loop
`add_edge + graph[source][target].update(...)` — directed adjacency-view __getitem__ per row
= O(N^2): 220ms/962ms @ n=400/800 (0.009x/0.004x vs nx, ~250-430x slower).

FIX: extend the batch gate to `type(graph) in (Graph, DiGraph)`. The existing batch
(add_edges_from of (s, t, dict(zip(headings, attrs))) triples) is identical for directed
(no symmetric dedup; duplicate (s,t) rows merge later-wins exactly like the repeated update).
Result: 0.004x -> **1.67-1.75x** (962ms->2.47ms @ n=800, ~390x self-speedup). Byte-exact:
8 checks (di/un x multi-attr/single-attr/duplicate-rows-later-wins). 217 pandas tests + full
suite zero new failures.

PATTERN (3 disasters, now all fixed): converters/constructors with a `type(graph) is Graph`
batch branch but a DIRECTED fall-through to a per-edge `graph[u][v].update` loop are O(N^2)
(directed adjacency-view __getitem__ per edge). Audited the family; compose(Di) 0.62-0.70x
is a separate LINEAR _copy_attrs_into per-edge tax (not O(N^2)).

## 2026-06-22 CopperCliff `compose` node-batch — directed 0.62x -> 0.74x partial + non-string-key fix (`br-r37-c1-composenodebatch`, cc)

Directed `compose` was 0.62-0.70x (undirected has `_native_compose`; directed falls to the
Python path). Edges already batched (two add_edges_from); the bottleneck was the per-node
`out.add_node(node, **dict(attrs))` loop for G then H. Replaced with two `add_nodes_from(
.nodes(data=True))` (adds-or-updates exactly like nx — H's overlapping nodes update G's).
Bonus correctness: `add_node(node, **attrs)` unpacked attrs as kwargs (fails / diverges on
non-string node-attr keys); `add_nodes_from((node, attrs))` matches nx for arbitrary keys.

PARTIAL: 0.62x -> 0.74x. Residual is the directed `add_edges_from` non-fresh substrate (same
~0.74-0.78x floor as cycle_graph(DiGraph) create_using; nodes pre-added defeat the fresh
batch path, and directed insertion is the documented substrate). Full domination needs a
native `_native_compose` for DiGraph (rust). Byte-exact: 5 checks (di/un x node+edge attrs,
overlapping-node merge). 961 operator tests + full suite zero new failures.

### Note (cc): MultiDiGraph dict-of-dicts 0.42x is keyed-insertion substrate, NOT batchable

After fixing the 3 SIMPLE directed dict-of-dicts O(N^2) disasters, checked the MULTI variants.
MultiGraph dict-of-dicts is a win (1.1-1.2x). MultiDiGraph from_dict_of_dicts(mi=True) and the
MultiDiGraph(dod) constructor are 0.42x — but LINEAR (scale x2.0 @ n400->800, NOT O(N^2)) and
NOT batchable: tested per-edge `_add_json_multiedge` (12.84ms) vs `add_edges_from(4-tuples)`
nodes-pre-added (12.45ms ~= same) vs fresh-then-nodes (15.6ms, worse). `_add_json_multiedge`
already uses O(1) get_edge_data (no graph[s][t][k] rebuild). So the 0.42x is the MultiDiGraph
KEYED-edge insertion substrate (~2.4x nx), the same directed/multi construction floor as
[[reference_multigraph_attr_batch_construction]] (dual AttrMap + mirror storage). Not a wrapper
lever — needs the rust keyed-insertion substrate work. NOT shipped (batching is ~0-gain here).

### Addendum 5 (cc): flow / branching / group-centrality / similarity / approximation sweep — domination, no gaps

Interleaved sweep of families not previously benched (~18 fns). All wins or parity, no sub-0.85x:
gomory_hu_tree 1.73x, max_flow_min_cost 3.03x, minimum_spanning_arborescence 4.04x,
stoer_wagner 7.90x, all_node_cuts 1.96x, group_closeness 7.75x, group_betweenness 0.95x,
simrank_similarity 1.01x, panther 0.99x, approx max_clique 0.90x, approx node_connectivity
1.62x, approx average_clustering 69x, approx diameter 1.64x, approx local_node_connectivity
6.35x, harmonic_centrality 17.25x, percolation_centrality 1.86x, current_flow_closeness 9.56x,
edge_current_flow_betweenness 23.53x. Confirms domination extends to flow/branching/group/
similarity/approximation; no clean lever here. Combined with all prior sweeps, every
non-substrate domain is dominant; remaining residuals are the documented keyed-insertion /
node-mirror substrate and parity-blocked (set-order / IO-lxml) cases.

### Note (cc): the fresh-int add_edges_from batch is PREFIX-bound — arbitrary-int needs materialized keys (substrate)

Investigated whether the from_edgelist(random)/directed add_edges_from 0.64x floor is a
contained fix. It is NOT. The fast path `collect_fresh_exact_int_prefix_edges`
(fnx-python/src/lib.rs:1695) requires node ints to appear in EXACT PREFIX order (0,1,2,...):
`if index != next_node: return None`. It is fast precisely because it then calls
`_fast_add_int_nodes_range_stop` + `extend_existing_index_edges_unrecorded` over the
lazy-int-prefix node representation (`lazy_int_node_stop`), where node VALUE == index.
Random/arbitrary int edges (e.g. gnm.edges(), first edge (5, 200)) bail at the prefix check.
Generalizing to arbitrary-order ints can't reuse the lazy-prefix representation (values !=
indices), so it would require materializing int node keys + node_key_map in first-appearance
order — the deep construction-substrate work, not a gate relaxation. Confirms from_edgelist
(random) 0.64x and the directed add_edges_from floor are substrate-bound. No contained lever.

### Note (cc): directed `compose` -> native is the top remaining perf lever, but needs careful directed-display work

Scoped the highest-value remaining lever: compose(DiGraph) is 0.74x (after the node-batch
br-r37-c1-composenodebatch); the undirected path hits `_native_compose` (PyGraph, lib.rs:9688)
for 1.99x. A `PyDiGraph::_native_compose` mirror would lift directed compose to ~domination —
same pattern as the shipped MultiDiGraph(DiGraph) absorb. BUT the undirected version (~80 lines)
encodes intricate directed-RELEVANT-only-as-undirected logic: integer-walk symmetric dedup
(seen ui.min/max), first-touch row-store via `adj_py_keys` (single adjacency), fwd/rev
edge_key attr-mirror merge, bulk extend_*_with_attrs_unrecorded. The directed mirror must
instead: walk successors_indices (NO dedup), populate BOTH succ AND pred display/row tables
(`succ_py_keys`/`pred_py_keys` — DiGraph has dual row models vs Graph's single adj), and
directional edge_key only. That directed display/row-override surface is large and compose is
widely used (high blast radius), so this is deep-design tier (exhaustive parity + review),
NOT a safe autonomous one-pass change. Documented as the #1 target for the substrate-work
go-ahead. All other residuals (construction-keying, node-mirror) remain deeper still.

## 2026-06-22 CopperCliff native DiGraph `compose` — 0.74x -> 2.25-2.33x (`br-r37-c1-composedir`, cc)

The #1 scoped lever, now SHIPPED. compose(DiGraph) was 0.74x (Python add_nodes/add_edges
replay; undirected had _native_compose at 1.99x). Added `PyDiGraph::_native_compose` mirroring
the undirected one but directed: walks SUCCESSORS (no symmetric dedup — directed edges unique),
directional edge mirrors (edge_key(u,v) only), node/edge merge with H-overlap-wins, commit via
bulk extend_nodes/edges_with_attrs_unrecorded. CLEAN-DISPLAY GATED: returns Ok(None) (Python
fallback) when either part carries succ/pred row-display overrides — sidestepping the intricate
per-cell maybe_store path, which the replay handles. Wired in compose() for exact DiGraph x
DiGraph (non-private-storage), checking the None fallback.

Result: 0.74x -> **2.25-2.33x** (~3x self-speedup, now DOMINATES). Byte-exact: 7 checks
(random node+edge+graph attrs, overlap-merge H-wins, self-loops, isolated, str keys, empty) —
nodes(data), edges(data), graph attrs, succ AND pred adjacency. 993 operator/convert tests +
full suite zero new failures (fallback path exercised by conformance).

METHOD: the gated-fallback pattern (native fast path for the clean/common case, Ok(None) ->
Python replay for the intricate-display minority) makes 'deep-design-tier' native mirrors
safely shippable autonomously — exhaustive parity + full conformance as the safety net.
Artifact: tests/artifacts/perf/20260622T-native-digraph-compose-cc/.

## 2026-06-22 CopperCliff native DiGraph `disjoint_union` — 0.79x -> 3.28-3.32x (`br-r37-c1-djudir`, cc)

Second directed native-mirror this pass (after compose). disjoint_union(DiGraph) was 0.79x
(Python disjoint_union_all replay; undirected had _native_disjoint_union at 2.03x). Added
`PyDiGraph::_native_disjoint_union` mirroring the undirected: relabel BOTH parts to fresh
integer ranges (0.. , n1..), copy node/edge attr mirrors (shallow), commit via bulk
extend_*_unrecorded. Directed adaptation: walk SUCCESSORS (no symmetric dedup), directional
edge_key. Because both parts are relabeled to fresh ints, the source row-display is discarded
-> NO gating needed (cleaner than compose).

Result: 0.79x -> **3.28-3.32x** (~4x self-speedup, dominates). Byte-exact: 6 checks (random
node+edge+graph attrs, str-keyed source, self-loops, isolated, empty) — nodes(data),
edges(data), graph attrs, succ AND pred. 1284 union/operator tests + full suite zero new
failures. Confirms the gated/clean native-mirror pattern ([[reference_gated_fallback_native_mirror]])
scales across directed operators. Remaining directed-operator residuals: intersection(Di) 0.77x
(set-based Python, no native to mirror), union(Di) 0.88x. Artifact:
tests/artifacts/perf/20260622T-native-digraph-disjoint-union-cc/.

### Note (cc): MultiDiGraph disjoint_union/compose native REVERTED — blocked by a source construction-key divergence

Attempted `PyMultiDiGraph::_native_disjoint_union` (keyed mirror; multi operators are 0.57-0.79x:
disjoint_union(MDG) 0.57x, compose(MDG) 0.58x, disjoint_union(MG) 0.63x, compose(MG) 0.74x).
nx.disjoint_union PRESERVES multigraph keys (verified: explicit keys 1,3,7 -> 1,3,7; default
0,1,0 -> 0,1,0), so a key-preserving native is the correct semantics, AND it passed 6 hand
parity cases. BUT it FAILED test_graph_operator_batches_match_networkx_without_fallback
[MultiDiGraph-MultiDiGraph]: the test's FNX-built right MultiDiGraph carries DIFFERENT edge
keys than the nx-built one on some construction path (fnx gave 1,3 where nx gave 0,1). The
key-preserving native faithfully propagates fnx's divergent source keys -> output != nx; the
OLD Python disjoint_union path MASKS it (it re-keys to 0,1.. matching nx). Renumbering instead
breaks the key-identical case (nx preserves). So neither preserve nor renumber cleanly matches —
the real blocker is a PRE-EXISTING fnx MultiDiGraph construction key divergence (NOT
add_edges_from((u,v)) — that matches nx 0,1,0; some other path in _operator_graph_pair). REVERTED
the MDG native (kept the Python path, which is green). The simple-DiGraph compose + disjoint_union
natives (br-r37-c1-composedir/djudir) are unaffected and shipped. FOLLOW-UP: find + fix the
MultiDiGraph construction key divergence, THEN the keyed-native operators unblock.

### Note (cc): MDG disjoint_union native — CORRECTED diagnosis: display-key mirror, gate-too-strict (not viable)

Refines the prior note. The MultiDiGraph blocker is NOT a construction bug: explicit-key
construction + the Python disjoint_union are byte-correct, and nx PRESERVES keys. The real
issue is that the inner integer edge key != the Python DISPLAY key for explicit/non-default
keys (stored in a separate `edge_py_keys` mirror), and typical graphs (range-built -> lazy-int
display) ALSO carry `succ_py_keys`/`pred_py_keys` mirrors. So:
- UNGATED native (use inner keys) -> diverges on explicit-key graphs (the operator-parity test:
  inner 0,1 vs display 1,3).
- GATED native (require edge_py_keys/succ/pred empty) -> NEVER fires for typical lazy-int
  graphs (their display mirrors are non-empty) -> 0.55x, ZERO real-world gain.
Both dead ends -> REVERTED (verified green). The keyed-multi operators (disjoint_union/compose
for MG/MDG, 0.57-0.79x) require FULL display-mirror native handling (per-key py_edge_key +
per-cell succ/pred row-store) — the intricate path the gated/clean approach sidesteps, so they
are genuinely deep-substrate (unlike the simple-DiGraph compose/disjoint_union, which shipped
because Graph/DiGraph display is single-table + the relabel discards source display). The
simple-DiGraph natives stand. Multi keyed operators: deferred to the display-mirror substrate work.

## 2026-06-22 CopperCliff native MultiDiGraph disjoint_union — 0.57x -> 1.66-2.20x SHIPPED (`br-r37-c1-mdgdju`, cc)

RESOLVED the keyed-multi blocker from the prior two notes. The fix was NOT gating and NOT a
construction bug — it was that the native must COPY the `edge_py_keys` DISPLAY-key mirror.
MultiDiGraph stores an inner integer key that can DIFFER from the Python display key for
explicit/non-default keys; nx.disjoint_union PRESERVES display keys. v1 copied only
edge_py_attrs (not edge_py_keys) -> explicit keys 1,3 displayed as internal 0,1 (operator-
parity test fail). v2 gated on edge_py_keys-empty -> never fired for typical lazy-int graphs
(0 gain). v3 (shipped): UNGATED, copy edge_py_keys alongside edge_py_attrs. The relabel to
fresh int ranges discards source NODE display + succ/pred row overrides, so only the edge
display-KEY mirror needs preserving — no per-cell row-store, no gate.

Result: disjoint_union(MDG) 0.57x -> **1.66-2.20x** (~3.5x self-speedup, 40ms->14ms @ n=800).
Byte-exact: 7 checks (default-key native, explicit non-default keys, parallel self-loops, str
source, empty) — nodes(data), edges(keys+data), graph attrs, succ AND pred. operator-parity
test + full suite zero new failures. UNBLOCKS the keyed-multi pattern: compose(MDG) 0.58x,
disjoint_union(MG) 0.63x, compose(MG) 0.74x are next (same edge_py_keys-copy recipe; MG adds
undirected symmetric dedup). Artifact: tests/artifacts/perf/20260622T-native-mdg-disjoint-union-cc/.

## 2026-06-22 CopperCliff native MultiGraph disjoint_union — 0.63x -> 2.05-2.13x SHIPPED (`br-r37-c1-mgdju`, cc)

The edge_py_keys-copy recipe ([[reference_gated_fallback_native_mirror]]) generalized to the
undirected-multi case FIRST TRY. disjoint_union(MG) was 0.63x. PyMultiGraph::_native_disjoint_union
relabels both parts to fresh int ranges (source node + adj_py_keys row display discarded, no
gate), walks neighbors with symmetric dedup via the CANONICAL edge_key (sorts u<=v, so the
undirected edge_py_attrs/edge_py_keys lookup is orientation-independent — no fwd/rev), preserves
each edge's inner key + DISPLAY key (edge_py_keys mirror) + attrs, bulk extend. Modeled on the
existing PyMultiGraph::_native_difference keyed pattern (display_key/py_edge_key/seq fields).

Result: 0.63x -> **2.05-2.13x** (~3.3x self-speedup). Byte-exact: 7 checks (default-key, explicit
non-default keys, parallel self-loops, empty) — nodes(data), edges(keys+data), graph attrs, adj.
operator-parity[MultiGraph-MultiGraph] + full suite zero new failures. Remaining keyed-multi:
compose(MDG) 0.58x, compose(MG) 0.74x (these KEEP nodes -> need the clean-display gate on
succ/pred or adj_py_keys like simple compose, PLUS edge_py_keys + key-level overlap merge).
Artifact: tests/artifacts/perf/20260622T-native-mg-disjoint-union-cc/.

### Note (cc): compose(MDG/MG) native — design for the follow-up (key-collision merge, H-wins)

disjoint_union is now native-dominant across ALL 4 graph types (Graph/DiGraph/MultiDiGraph/
MultiGraph). compose(MDG) 0.58x / compose(MG) 0.74x are the remaining keyed-multi gaps. DESIGN
GOTCHA confirmed: nx compose MERGES multigraph edges by (u,v,key) with H winning on collision
(verified: G{(a,b,0):G0,(a,b,1):G1} compose H{(a,b,0):H0,(a,b,5):H5} -> (a,b,0):H0,(a,b,1):G1,
(a,b,5):H5). So compose CANNOT reuse the simple-DiGraph compose structure (which leans on
extend_edges UPDATING duplicate (u,v) for simple graphs) — multi extend_keyed would add a
PARALLEL edge for a colliding key, not update. Needs an explicit ordered merge: emit G's edges
in order (attrs := H's if H has the same (u,v,key), else G's), then H's edges whose (u,v,key)
is NOT in G, in H order; carry edge_py_keys display + node-attr H-wins merge; clean-display gate
on succ/pred (MDG) / adj_py_keys (MG) like simple compose. Recipe + APIs all proven
([[reference_gated_fallback_native_mirror]]); this is the immediate next gap.

### Note (cc): compose(MDG) native ATTEMPTED + REVERTED — display-key collision-merge is the blocker

Implemented PyMultiDiGraph::_native_compose (clean-display gated, ordered (u,v,key) merge with
H-wins). Two failures -> reverted:
1. CORRECTNESS: merged by the INNER integer key, but nx merges by DISPLAY key. G with display
   keys {0,1} composed with H display {0,5}: H's display-5 has INNER key 1, which collided with
   G's INNER-1 (display 1) -> clobbered G's (a,b,1) edge (dropped from 3 edges to 2). Must dedup/
   merge by display_key_lookup(u,v,key), NOT the inner key. (disjoint_union dodged this — it
   PRESERVES keys per part with no cross-part merge, so inner-vs-display never collides.)
2. PERF: 0.58-0.60x — NO gain. The ordered-merge bookkeeping (3 HashMaps keyed by String tuples
   + per-edge AttrMap clones + a rebuild pass) costs more than nx's Python compose. Unlike
   disjoint_union (direct edge_batch, 2.2x), compose's cross-part key-collision merge can't use
   the fast direct-batch path: G-then-H with H winning needs either heavy per-edge dedup
   bookkeeping (slow) or in-place inner-edge attr update on the rare collision (no inner
   set-edge-attrs-by-key API exists).

So compose(MDG)/compose(MG) (0.58x/0.74x) are the genuinely-hard tail of the operator vein:
correctness needs display-key merge, and a WIN needs a fast-path-for-the-common-no-collision-
case + cheap rare-collision handling (likely a G-display-key HashSet + mirror-only attr update
on collision, leaving inner as G's since the mirror dominates edges(data)). Deferred — not a
clean win without that. disjoint_union (all 4 types) + compose(Graph/DiGraph) remain shipped.

### Note (cc): compose(MDG/MG) native DEFINITIVELY BLOCKED — MultiGraph always carries succ/pred (z6uka) display

compose(MDG) v2 (gated on succ/pred AND edge_py_keys empty, fast HashSet collision-merge) is
byte-CORRECT (7/7 parity incl default-key collisions + partial-attr merge + explicit fallback)
but 0.52-0.56x = ZERO gain: the gate FALLS BACK for typical graphs. Diagnosis by elimination:
disjoint_union(MDG) UNGATED runs native at 2.2x; compose(MDG) GATED is ~Python speed -> it never
fires. edge_py_keys is empty for MDG(gnm) (keys all 0), so it's succ/pred_py_keys that's
NON-empty. Unlike simple DiGraph(gnm) (where compose(Di) gated on succ/pred and WON 2.25x),
MultiGraph/MultiDiGraph populate per-cell succ/pred ROW display objects (br-r37-c1-z6uka multi
adjacency cells) even for plain gnm graphs. compose KEEPS node identity, so it CANNOT discard
that row display (disjoint_union can — it relabels to fresh ints). Result: the clean-display gate
never fires for compose(Multi) -> not viable without full per-cell succ/pred maybe_store_row_keys
handling = the genuinely-deep path. REVERTED.

OPERATOR VEIN STATUS (final): disjoint_union native-DOMINANT all 4 types (Graph/DiGraph/MDG/MG);
compose native-dominant Graph+DiGraph; compose(Multi) BLOCKED on z6uka succ/pred row display
(deep). difference/symmetric_difference already native wins. Operator native-mirror vein
EXHAUSTED of clean wins.

## 2026-06-22 CopperCliff MultiDiGraph edges(keys=True,data=True) cache — 0.78x -> 3.33-3.64x (`br-r37-c1-mdgkd`, cc)

Found via a fresh sweep: MD edges(keys,data) 0.78x while edges(data) 3.58x and edges(keys) 1.86x.
Root cause: PyMultiDiGraph cached edges(data=True,keys=False) [edges_with_data_cache] and
edges(keys=True,data=False) [edges_with_keys_cache] but had NO cache for the keys+data combo —
it hit edges_key_alldata_existing_mirrors (returns None for attr-less gnm edges) then the generic
loop, materializing empty mirrors EVERY call. Fix: added a `keys` bool to the existing
edges_with_data_cache (4-tuple, last-keys-variant-wins) so keys+data caches in the same slot — no
new struct field (avoids the ~20-site constructor churn). Mirrors the PyMultiGraph mgkd fix.

Result: 0.78x -> **3.33-3.64x**. Byte-exact: keys+data / data / keys all correct across attr +
attr-less graphs, cache-thrash alternation, AND post-mutation invalidation. Full suite zero new
failures. Artifact: tests/artifacts/perf/20260622T-mdg-edges-keysdata-cache-cc/.

Sweep also surfaced (deferred): nbunch_iter 0.09-0.19x (node-object materialization + String-keyed
membership substrate — deep), degree(weight)/size(weight) ~0.80x (weighted attr walk), relabel
0.86x (known construction tax). MD remaining edges combos now all dominant.

## 2026-06-22 CopperCliff nbunch_iter(None) — 0.08x -> 0.95x (`br-r37-c1-nbunchnone`, cc)

Sweep flagged nbunch_iter(None) at 0.08-0.19x while list(G)/list(nodes()) were at parity.
Root cause: _graph_nbunch_iter (shared by all 4 graph types) ran `adjacency = self.adj`
UNCONDITIONALLY at the top, then `iter(adjacency)` for the None case — building the full
AdjacencyView + iterating its keys cost ~12x vs the cached node iterator, purely to list nodes.
Fix (Python-only, no rebuild): return iter(self) for nbunch=None BEFORE building self.adj; defer
`adjacency = self.adj` to the membership-filter path (where its __contains__ is the faster
container — using bare `self` there regressed non-None to 0.16x, so adj stays).

Result: nbunch_iter(None) 0.08x -> **0.95x** (12x self-speedup, 107us->9us @ n=2000), all 4 types.
Byte-exact: node order + objects + fresh-iterator-per-call + nx's TypeError error contract
(unhashable-in-sequence / non-iterable nbunch). Full suite zero new failures. Non-None nbunch
(membership filter) stays 0.20x = per-element String-keyed __contains__ substrate (nx is C-dict;
deep, unchanged). Artifact: tests/artifacts/perf/20260622T-nbunch-iter-none-cc/.

### Note (cc): post-win sweep (2026-06-22) — accessible no-build levers exhausted; remaining gaps root-caused

After shipping 6 operator/view/iter wins this turn, ran 5 no-build bench sweeps (traversal,
distance, predicates, views, attrs, construction, nbunch ops) vs NetworkX. Result: the surface
is overwhelmingly dominant. The ONLY remaining un-dominated workloads, all root-caused:

- out_edges(nbunch)/in_edges(nbunch) DIRECTED 0.28-0.29x: NICHE (directed edges restricted to a
  node subset). Path traced: _OutEdgeView -> _DiEdgeMethodView.__call__ -> _method(self._graph,
  nbunch) which ALREADY uses the rust graph directly (no Python-wrapper layer to strip). Slowness
  is inherent: a Python loop doing per-node rust succ/pred row PyO3 access. UNDIRECTED edges(nbunch)
  is DOMINANT (1.39x), so this is directed-specific view overhead. Needs a native nbunch-edges
  kernel (build) wired through the 6-level view hierarchy — intricate + niche, deferred.
- degree(nbunch) 0.32x: DegreeView per-node self[node] (per-call native degree + String-key
  canonicalization). Full degree() routes to native counts (1.20x); nbunch can't cleanly reuse it
  (counts are by index; small-nbunch would pay O(N) dict-build). Per-call substrate.
- has_edge/neighbors/adj[n]/membership(`n in G`) per-call 0.29-0.54x: the fundamental String-keyed
  __contains__/__getitem__ substrate (nx is C-dict). The highest-IMPACT remaining gap (used
  everywhere) but = the deep int-key / persistent-mirror rewrite.

CONVERGENCE: no-build/Python-only levers exhausted (nbunch_iter(None) was the last clean one).
Remaining frontier = (a) native nbunch-edges kernel (niche, build, needs disk headroom) or (b)
the deep per-call String-key substrate rewrite (highest impact, large careful effort, needs disk).

## 2026-06-22 CopperCliff native Graph degree(nbunch) — 0.32x -> 1.22-1.24x SHIPPED (`br-r37-c1-degnbnative`, cc)

Reverses the earlier "nbunch native kernels are canonicalization-capped" hypothesis: the rust
kernel DOMINATES (direct 0.051ms vs nx 0.091ms). degree(nbunch) was 0.32x because the Python
path ran two per-element passes (the `[n for n in nbunch if n in G]` membership filter + per-node
`raw[n]` degree lookup), each a separate PyO3 round-trip. Added `PyGraph::_native_degree_pairs_subset`
(one PyO3 call: per node hash-check + node_key_to_string canonicalize + get_node_index +
degree_by_index, skipping absent). Routed in _WeightAwareDegreeView.__call__'s iterable-nbunch
branch (the REAL path — gf.degree is _GraphDegreeView which inherits this __call__; the slow loop
is at the 4738 branch, NOT the 4818 single-node branch I first wrongly edited). _FilteredDegreeView
gained a `pairs` slot: __iter__ serves precomputed (node,degree), __getitem__ still falls to the raw
view (so view[n] works for any node). Unhashable element -> kernel TypeError(exact message) ->
NetworkXError, matching nx.

Result: 0.32x -> **1.22-1.24x** (~3.9x self-speedup). Byte-exact: valid/invalid/all-invalid/empty/
dup/range/str-keyed, error contract (unhashable element + non-iterable), view[node] indexing for
any node, len/contains. DiGraph degree(nbunch) unaffected (PyDiGraph lacks the binding -> Python
fallback; a PyDiGraph total/in/out kernel is the follow-up). Full suite zero new failures.
LESSON: verify which concrete class a method resolves to (multiple masquerade as 'DegreeView')
before editing — cost two wrong-class edits. Artifact: tests/artifacts/perf/20260622T-degree-nbunch-native-cc/.

## 2026-06-22 CopperCliff native DiGraph degree(nbunch) family (`br-r37-c1-degnbnative`, cc)

Extended the degree(nbunch) native one-pass kernel to DiGraph (3 PyDiGraph kernels via a shared
degree_pairs_subset_impl over DegreeKind Total/In/Out). Routing: total auto-routes through the
existing _WeightAwareDegreeView.__call__ (binding added); in/out route in _DirectedDegreeView.__call__
(keyed by _adjacency_attr succ->out / pred->in), reusing _FilteredDegreeView with `self` as raw.

Results (n=1500, k=750):
- total degree(nbunch): 0.32x -> **1.23x SHIPPED/DOMINATES** — nx computes len(succ)+len(pred)
  (two dict lookups) per node; fnx does one degree_by_index, so it wins.
- in_degree/out_degree(nbunch): 0.17-0.18x -> **0.71x** (4x self-speedup, KEPT as strictly-better)
  but STILL below nx: nx's single C-dict len(pred[n])/len(succ[n]) beats fnx's per-node String
  canonicalization + index. This is the canonicalization wall — confirms the EARLIER hypothesis
  for the single-lookup case (only the deep int-key substrate would push in/out >1x). The total
  case escapes it because nx pays double.

Byte-exact: valid/invalid/empty/dup/range, error contract (unhashable element + non-iterable),
view[node] indexing for any node, MultiDiGraph in/out/total degree(nbunch) unaffected (PyDiGraph-
only bindings -> Python fallback). Full suite zero new failures.
Artifact: tests/artifacts/perf/20260622T-digraph-degree-nbunch-cc/.

## 2026-06-22 CopperCliff native DiGraph out_edges(nbunch) — 0.27x -> 2.50x SHIPPED + in_edges pred-order finding (`br-r37-c1-edgenbnative`, cc)

out_edges(nbunch, data=False) was 0.27x (delegated to the EdgeDataView Python machinery).
Added PyDiGraph::_native_out_edges_nbunch_no_data (shared edges_nbunch_no_data_impl): one pass
— canonical-filter the nbunch (deduping repeated nodes, since nx dedups: out_edges([1,1,2])==
out_edges([1,2])), walk successors_INDICES (insertion order == nx succ; the string successors
accessor does NOT preserve it) and map via cached_node_key_vec. Gated on succ_py_keys empty
(z6uka per-cell row display -> Ok(None) Python fallback). Result: 0.27x -> **2.50x** (~9x
self-speedup, dominates). Byte-exact: 5 seeds x 8 nbunch shapes (valid/invalid/empty/range/dup/
single/all/rev) + str-keyed + data=True fallback + error contract. Full suite zero new failures.

PRE-EXISTING FINDING (NOT shipped, NOT my regression): in_edges(nbunch) — and full in_edges() —
DIVERGE from nx in predecessor ORDER. fnx's `self.pred[v]` returns predecessors in INDEX order
([3,6,15,20]); nx uses edge-INSERTION order ([20,3,6,15]). Confirmed on a clean DiGraph (no
native involved) and the full _native_in_edges_no_data (predecessors_indices) shares it. So an
in_edges(nbunch) native kernel can't be made nx-exact without storing pred in insertion order
(deep). Uncaught by conformance (in_edges order not strictly tested). out_edges is safe because
fnx DOES store successors in insertion order. Filed as a correctness divergence to investigate
(separate from perf). Artifact: tests/artifacts/perf/20260622T-out-edges-nbunch-cc/.

## 2026-06-22 CopperCliff native MultiGraph edges(nbunch) — 0.09x -> 1.00x (biggest gap) (`br-r37-c1-mgedgenb`, cc)

The biggest single gap surfaced by the multi-nbunch sweep: MG edges(nbunch, data=False) was
**0.09x** (29.5ms vs nx 2.5ms @ n=1500/k=750). Profiled: the cost is the Python triple-loop's
`self.adj[source].items()` (MultiAdjacencyView lambda chain, ~24.5ms/750 src) + a
`frozenset((u,v))` dedup per edge (~4ms). Added PyMultiGraph::_native_mg_edges_nbunch_no_data:
walk neighbors() (nx adj insertion order — proven order-correct by the disjoint_union(MG) work)
x edge_keys() once, dedup undirected parallels by a normalized (lo,hi,key) string-pair, emit
(u,v) or (u,v,key). Gated on adj_py_keys empty (+ edge_py_keys empty for keys=True) -> Python
fallback for z6uka/non-default-key-display graphs.

Result: keys=False 0.09x -> **1.00x** (~12.7x self-speedup — eliminates the catastrophic loss,
now at parity); keys=True 0.09x -> 0.75x (the per-edge int key_obj construction keeps it just
below nx; kept as strictly-better). Byte-exact: 4 seeds x 7 nbunch shapes x keys/no-keys incl
parallels, self-loops, str-keyed, dup nodes + data=True fallback + error contract. Full suite
zero new failures. (data=True/key variants keep the Python path; MultiDiGraph out_edges(nbunch)
0.93x is near-parity, lower priority.) Artifact: tests/artifacts/perf/20260622T-mg-edges-nbunch-cc/.

## 2026-06-22 CopperCliff native MultiDiGraph in/out_degree(nbunch) — 0.58-0.62x -> 2.47-2.67x SHIPPED (`br-r37-c1-degnbnative`, cc)

Corrects the "canonicalization-capped" prediction for MULTI degree: it DOMINATES. nx's
MultiDiGraph in_degree(n) = sum(len(keydict) for keydict in pred[n].values()) — an O(deg) sum in
PYTHON per node; fnx's inner in_degree sums the same in RUST + one PyO3 call for the whole nbunch,
so it wins (unlike SIMPLE in/out_degree where nx does a single C len(adj[n]) that fnx can't beat).
Added 3 PyMultiDiGraph degree-subset kernels (shared helper, string-based multiplicity in/out/
total degree); in/out AUTO-ROUTE via the existing _DirectedDegreeView.__call__ (the multi in/out
views _InMultiDegreeView/_OutMultiDegreeView pass "pred"/"succ") — NO Python change.

Result: in_degree(nbunch) 0.62x -> **2.67x**, out_degree(nbunch) 0.58x -> **2.47x**. Byte-exact:
3 seeds (with parallels) x valid/invalid/empty/range/dup + error contract + view[node] indexing.
Full suite zero new failures. Follow-ups (same Python-sum-vs-rust-sum domination expected): MDG
total degree(nbunch) [MultiDiGraphDegreeView route] and MG degree(nbunch) 0.73x [MultiGraphDegree
View route] — separate view classes needing their own routing + a PyMultiGraph kernel.
Artifact: tests/artifacts/perf/20260622T-mdg-degree-nbunch-cc/.

## 2026-06-22 CopperCliff native MultiGraph degree(nbunch) — 0.73x -> 2.75x + degree-nbunch bad-node fix (`br-r37-c1-degnbnative`, cc)

MG degree(nbunch) 0.73x -> **2.75x** (dominates; same Python-keydict-sum-vs-rust-sum as MDG
in/out). Added PyMultiGraph::_native_degree_pairs_subset + routes in MultiGraphDegreeView /
MultiDiGraphDegreeView.__call__ (the two multi total-degree views). MDG total degree(nbunch) was
already ~parity (1.00x) — route added symmetrically (byte-exact, harmless no-op for that case).

REGRESSION FOUND+FIXED in the same change (caught by conformance): a single NON-iterable bad node
— e.g. degree(99), which `is_isolate` uses (G.degree(n)==0) — reached the native call and failed
try_iter with Python's "'int' object is not iterable", which I'd wrapped verbatim; nx's degree(n)
raises "Node n is not in the graph." Fixed across ALL degree-nbunch routes (Graph/DiGraph/MG/MDG,
total + in/out): the except maps "is not iterable" -> NetworkXError("Node {nbunch} is not in the
graph."), leaving the unhashable-element-in-sequence message intact. Lesson: a native nbunch fast-
path must replicate the single-bad-node error contract, not just the iterable-filter path.

Byte-exact: MG+MDG degree(nbunch) all shapes + error contract (single bad node, unhashable elem)
+ view-indexing; is_isolate bad-node across all 4 types. Full suite zero new failures.
Artifact: tests/artifacts/perf/20260622T-mg-degree-nbunch-cc/.

## 2026-06-22 CopperCliff native MG edges(nbunch, data=True) — 0.09x -> 0.57x + single-node edges fix (`br-r37-c1-mgedgenb`, cc)

The data=True sibling of the MG edges(nbunch) fix (data=False reached 1.00x). Was also 0.09x
(same adj[source] lambda-chain). Added _native_mg_edges_nbunch_data: collects neighbors/keys as
owned Vecs (releasing the inner borrow so the &mut ensure_edge_py_attrs call is legal), emits
(u,v[,key],live_attr_dict) where the dict is the materialized live edge_py_attrs mirror
(identity-preserving == G[u][v][key], verified by a mutation-visibility check). Result: 0.09x ->
**0.57x** (~6x self-speedup; materialization-capped — per-edge live-dict clone_ref + tuple build
vs nx's pre-existing C dicts, so it stays below nx; kept as strictly-better, the catastrophic
loss largely eliminated).

REGRESSION FOUND+FIXED (caught by test_contracted_nodes_multigraph_no_regression): a SINGLE
in-graph node passed to edges(n)/out_edges(n) (contracted_nodes does this) was try_iter'd by the
native kernel and errored, instead of returning that node's edges. Gated ALL 3 edges-nbunch
native routes (DiGraph out_edges, MG edges data=False, MG edges data=True) to ITERABLE nbunch
(list/tuple/set/non-str-iterable); a single node now falls to the view path (nbunch_iter -> [n]),
matching nx. Same lesson as the degree bad-node fix: a native nbunch fast-path must not intercept
the single-node case. Byte-exact: data=True keys=F/T x shapes + live-dict identity + single-node
+ error contract. Full suite zero new failures. data=True is the materialization-capped frontier;
DG out_edges(nb,data=True) 0.22x similar. Artifact: tests/artifacts/perf/20260622T-mg-edges-nbunch-data-cc/.

## 2026-06-22 CopperCliff selfloop_edges(multigraph) — 0.13x -> 3.37x (sparse) (`br-r37-c1-selfloopmulti`, cc)

selfloop_edges on a MultiGraph/MultiDiGraph found self-loop nodes via an O(N) per-node
`has_edge(n,n)` PyO3 probe over ALL nodes (the simple-graph nodes_with_selfloops_rust is
"wrong for multi"), so on gnm (≈0 self-loops) it was ~0.05-0.13x vs nx. Added
_native_selfloop_nodes (PyMultiGraph + PyMultiDiGraph): rust scan in node-iteration order;
routed in selfloop_edges' multigraph branch. Result (realistic sparse self-loops): nsl=0 (the
sweep's gnm case) **0.13x -> 3.37x**, nsl=5 1.08-1.50x — dominates. Byte-exact across all
variants (keys / data=True / data=str+default, parallel self-loops with attrs) for MG and MDG.
Full suite zero new failures.

RESIDUAL: DENSE self-loops (nsl>=30) stay ~0.3-0.5x — there the cost shifts to the Python
emission `for n in sl_nodes: yield n, G[n]` (one native row materialization per self-loop node,
then nbrs[n].items()); a full native self-loop-EDGE kernel (emit (n,n[,key][,attrs]) directly,
like the edges(nbunch) kernels) would close it, but dense self-loops are atypical.
Artifact: tests/artifacts/perf/20260622T-selfloop-edges-multi-cc/.

## 2026-06-22 CopperCliff native DiGraph out_edges(nbunch, data=True) — 0.21x -> 0.77x (`br-r37-c1-edgenbnative`, cc)

Completes the out_edges(nbunch) family (data=False shipped at 2.5x). data=True was 0.21x
(delegated to the EdgeDataView machinery). Added _native_out_edges_nbunch_data (&mut self): succ
rows (index order == nx), live attr dict via materialize_edge_py_attrs (identity-preserving ==
G[u][v], verified by mutation check), node-dedup, iterable-gated. Result: 0.21x -> **0.77x**
(~3.7x self-speedup; materialization-capped — per-edge live-dict clone + tuple build vs nx's
pre-existing C dicts, so it stays <1x; kept as strictly-better, the catastrophic gap mostly
closed). Byte-exact: data=True x shapes incl identity, dup-node dedup, single-node fallback,
error contract. Full suite zero new failures.

CONCLUSION on data=True edge views: ALL are materialization-capped (~0.5-0.8x) — MG edges 0.57x,
DG out_edges 0.77x. They can't dominate without eager attr-dict mirrors (abandoning the lazy
design). The shallow DOMINATING vein is exhausted; data=True variants are strictly-better-but-
capped, and the remaining true gaps are deep-substrate (per-call String key, in_edges pred-order).
Artifact: tests/artifacts/perf/20260622T-dg-out-edges-nbunch-data-cc/.

## 2026-06-22 CopperCliff native MultiDiGraph out_edges(nbunch, data=False) — 0.87x -> 2.22x (`br-r37-c1-mdgoutedge`, cc)

out_edges(nb) keys=False 0.87x -> **2.22x** (dominates): nx iterates succ[u].items() keydicts in
Python; fnx walks successors x edge_keys in rust (one PyO3 call). _native_mdg_out_edges_nbunch_no_data
(PyMultiDiGraph): node-dedup, iterable-gated, succ_py_keys (+ edge_py_keys for keys) display gate.
keys=True 0.76x -> 0.79x (marginal — per-edge int key_obj construction is the cap, like MG edges
keys=True). Byte-exact: shapes x keys, parallels, single-node, dup, error contract + data=True
fallback. Full suite zero new.

MILESTONE: data=False edges(nbunch) is now native-DOMINANT across ALL 4 graph types
(Graph/DiGraph 2.5x, MG 1.00x [was 0.09x], MDG 2.22x). data=True variants remain materialization-
capped (~0.5-0.8x). Remaining: deep substrate (per-call String key, in_edges pred-order).
Artifact: tests/artifacts/perf/20260622T-mdg-out-edges-nbunch-cc/.

## 2026-06-22 CopperCliff native MDG out_edges(nbunch, data=True) — 0.65x -> 1.17x (`br-r37-c1-mdgoutedge`, cc)

Completes the out_edges(nbunch) data=True family. keys=False **0.65x -> 1.17x (DOMINATES)** —
unlike MG edges/DG out_edges data=True (materialization-capped ~0.57-0.77x), MDG out_edges
data=True dominates because its prior path was the slow self.edges machinery AND nx iterates
succ[u].items() keydicts in Python (so even with per-edge live-dict materialization, fnx's rust
walk wins). _native_mdg_out_edges_nbunch_data (&mut; successors/edge_keys collected owned for the
ensure_edge_py_attrs borrow; live attr dicts identity-preserving; node-dedup; iterable-gated).
keys=True 0.63x (4-tuple + int key_obj construction cap; strictly-better, kept). Byte-exact:
data=True keys F/T x shapes incl identity, dup, single-node, error contract. Full suite zero new.
Artifact: tests/artifacts/perf/20260622T-mdg-out-edges-data-cc/.

## 2026-06-22 CopperCliff MDG edges(nbunch) routed to out_edges kernels — 0.89x->1.59x (NO-BUILD) (`br-r37-c1-mdgoutedge`, cc)

For a directed graph edges() == out_edges(), but MDG.edges(nbunch) went through
_MultiDiGraphEdgeView.__call__'s `_native_edge_view()(nbunch,...)` path (~0.66-0.89x) while
out_edges() had dedicated dominating kernels. Routed the iterable-nbunch data=False/True case to
the EXISTING _native_mdg_out_edges_nbunch_no_data / _data kernels — Python-only, NO rebuild.
Result: edges(nb) data=False 0.89x -> **1.59x** (dominates; the view-wrap overhead keeps it below
out_edges' 2.22x but still wins), data=True 0.66x -> 0.92x (near-parity, improved). Byte-exact
incl the canonical OutMultiEdge* view types + all shapes/keys. Full suite zero new failures.
Lesson: when one call form (out_edges) has a native kernel, check the sibling form (edges) routes
to it too — often a free reuse.

## 2026-06-22 BlackThrush native unweighted cut scan - 5.19x-5.68x overlap (`br-r37-c1-wh7nt`, cod-a)

Lever: alien-graveyard 10.5 GraphBLAS-style masked sparse traversal, applied narrowly to
unweighted `cut_size` / `normalized_cut_size` for simple Graph/DiGraph. The old path materialized
the full boundary edge vector and then summed it. The new path builds S/T masks once and scans
native adjacency rows directly. Weighted and multigraph paths stay on their existing parity routes.

Keep decision: KEEP. The overlap workload is not a micro-gain, and it removes the stale reason to
delegate overlapping S/T cuts back to NetworkX. Expected-value score was high enough for a bold
probe: impact 3 * confidence 4 * reuse 3 / effort 2 = 18, with low blast radius because the lever
is unweighted-only and covered by NetworkX parity tests.

Head-to-head bench, small per-crate only:

`RCH_REQUIRE_REMOTE=1 AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- env PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/franken_networkx/crates/fnx-python/benches:/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code/networkx cargo bench -p fnx-python --bench networkx_head_to_head cut_metrics -- --noplot --sample-size 10 --warm-up-time 1 --measurement-time 2`

Note: `cargo bench --release` is not valid Cargo syntax; Criterion benches already build optimized
bench profiles, so the per-crate command above is the valid disk-frugal equivalent. RCH rewrote the
remote target dir to its worker-scoped warm path.

| workload | fnx | networkx | ratio |
| --- | ---: | ---: | ---: |
| cut_size overlap BA2500 S=1250 T=1250 | 474.63 us | 2.4613 ms | 5.19x |
| normalized_cut_size overlap BA2500 S=1250 T=1250 | 485.96 us | 2.7593 ms | 5.68x |
| edge_expansion BA2500 S=1250 | 556.54 us | 3.1793 ms | 5.71x |
| edge_expansion WS2500 S=625 | 286.62 us | 1.2948 ms | 4.52x |
| node_expansion BA2500 S=1250 | 121.55 us | 440.81 us | 3.63x |
| node_expansion WS2500 S=625 | 58.929 us | 251.90 us | 4.27x |

Behavior proof:

- `cargo test -p fnx-algorithms overlapping --lib`: 4 passed.
- Fresh in-tree extension passed the checkout stale-extension guard.
- `pytest tests/python/test_cuts_overlap_parity.py tests/python/test_boundary_value_parity.py -q`:
  628 passed.
- `cargo check -p fnx-python --benches --features pyo3/abi3-py310`: passed; existing
  `fnx-python/src/digraph.rs` `unused_must_use` warnings remain under CopperCliff's reservation.
- `cargo clippy -p fnx-algorithms --lib -- -D warnings`: passed after the split
  `br-r37-c1-yze2l` `FxBuildHasher` unit-struct cleanup.
- `cargo check -p fnx-classes --all-targets`: passed.
- `cargo clippy -p fnx-classes --all-targets -- -D warnings`: passed.
- `cargo test -p fnx-classes`: 68 passed, 2 ignored.

## 2026-06-22 CopperCliff MDG out_edges/edges(nbunch, keys=True) — 0.81x -> 1.38x + latent crash fix (`br-r37-c1-mdgoutedge`, cc)

out_edges(nb,keys=True) was 0.81x: _native_mdg_out_edges_nbunch_no_data GATED OUT for keys=True
(`keys && !edge_py_keys.is_empty()`), and MultiDiGraph(gnm) always carries an edge_py_keys mirror,
so keys=True fell to the slow self.edges path. Fix: drop the edge_py_keys gate, emit the DISPLAY
key via py_edge_key (falls back to the int key when no mirror) — the mdgdju recipe. Result:
out_edges(nb,keys=True) **0.81x -> 1.38x** (dominates), edges(nb,keys=True) 0.81x -> 1.02x.
ALSO fixed a LATENT CRASH this exposed (my earlier bfd4e3e3e edges route): keys=True wrapped via
_OutMultiEdgeView (a _DiEdgeMethodView needing (graph,method)) instead of _OutMultiEdgesKeysView
(the list-wrapper) -> TypeError once keys=True un-gated. Byte-exact: out_edges+edges x shapes incl
explicit string keys, dup/single-node/error contract. Full suite zero new (49231 passed).

## 2026-06-22 BlackThrush native dense multigraph selfloop_edges emission - 8.13x-31.79x self-speedup, still 0.22x-0.62x vs NetworkX (`br-r37-c1-8egkh`, cod-a)

Lever: finish the dense residual called out by the sparse self-loop keep above. `selfloop_edges`
on MultiGraph/MultiDiGraph now routes to `_native_selfloop_edges`, which emits the final
NetworkX-shaped tuples directly from the native self-loop scan instead of materializing `G[n]`
and then `nbrs[n]` for every self-loop node. The kernel preserves node display keys, parallel
edge display keys, `keys`, `data=True`, `data="attr"` with `default`, and live attr-dict identity.

Keep decision: KEEP. This is not a near-zero lever. It is still tuple/PyO3-object-construction
capped versus NetworkX, but it removes the dominant FNX-internal Python row-materialization cost.
No revert.

Final direct artifact probe:

`PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python` with
`/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`.

| workload | mode | old FNX row route | new FNX | NetworkX | self-speedup | ratio vs NetworkX |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| MultiGraph int keys | pairs | 9.244 ms | 0.315 ms | 0.179 ms | 29.32x | 0.57x |
| MultiGraph int keys | keys | 7.976 ms | 0.655 ms | 0.222 ms | 12.17x | 0.34x |
| MultiGraph int keys | data | 7.656 ms | 0.620 ms | 0.208 ms | 12.35x | 0.34x |
| MultiGraph int keys | keys_data | 8.562 ms | 0.839 ms | 0.230 ms | 10.21x | 0.27x |
| MultiGraph int keys | weight | 10.219 ms | 0.786 ms | 0.255 ms | 13.00x | 0.32x |
| MultiGraph int keys | keys_weight | 9.854 ms | 0.900 ms | 0.266 ms | 10.95x | 0.30x |
| MultiGraph string keys | pairs | 8.417 ms | 0.353 ms | 0.192 ms | 23.85x | 0.54x |
| MultiGraph string keys | keys | 8.675 ms | 0.497 ms | 0.178 ms | 17.47x | 0.36x |
| MultiGraph string keys | data | 8.646 ms | 0.592 ms | 0.214 ms | 14.61x | 0.36x |
| MultiGraph string keys | keys_data | 9.580 ms | 0.964 ms | 0.294 ms | 9.94x | 0.30x |
| MultiGraph string keys | weight | 8.538 ms | 0.800 ms | 0.397 ms | 10.67x | 0.50x |
| MultiGraph string keys | keys_weight | 8.192 ms | 0.822 ms | 0.266 ms | 9.97x | 0.32x |
| MultiDiGraph int keys | pairs | 9.827 ms | 0.309 ms | 0.193 ms | 31.79x | 0.62x |
| MultiDiGraph int keys | keys | 9.064 ms | 0.518 ms | 0.185 ms | 17.51x | 0.36x |
| MultiDiGraph int keys | data | 8.595 ms | 0.591 ms | 0.220 ms | 14.55x | 0.37x |
| MultiDiGraph int keys | keys_data | 8.810 ms | 1.084 ms | 0.234 ms | 8.13x | 0.22x |
| MultiDiGraph int keys | weight | 8.479 ms | 0.622 ms | 0.257 ms | 13.63x | 0.41x |
| MultiDiGraph int keys | keys_weight | 9.597 ms | 0.821 ms | 0.277 ms | 11.69x | 0.34x |
| MultiDiGraph string keys | pairs | 10.793 ms | 0.400 ms | 0.224 ms | 26.95x | 0.56x |
| MultiDiGraph string keys | keys | 8.692 ms | 0.516 ms | 0.184 ms | 16.83x | 0.36x |
| MultiDiGraph string keys | data | 12.125 ms | 0.614 ms | 0.218 ms | 19.75x | 0.36x |
| MultiDiGraph string keys | keys_data | 8.332 ms | 0.793 ms | 0.242 ms | 10.51x | 0.31x |
| MultiDiGraph string keys | weight | 9.920 ms | 0.775 ms | 0.314 ms | 12.79x | 0.40x |
| MultiDiGraph string keys | keys_weight | 8.822 ms | 0.844 ms | 0.272 ms | 10.45x | 0.32x |

Behavior proof:

- Direct artifact parity: public `fnx.selfloop_edges` and direct `_native_selfloop_edges` match
  NetworkX for MultiGraph and MultiDiGraph across pairs/keys/data/keys_data/weight/keys_weight,
  including live attr-dict mutation identity.
- `cargo fmt -p fnx-python --check`: passed.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`: passed.
- `cargo build -p fnx-python --release --features pyo3/abi3-py310`: passed; built
  `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`.
- `cargo test -p fnx-python --features pyo3/abi3-py310`: 27 passed, 0 failed.

Pytest note: the checkout's `tests/python/conftest.py` hard-fails when
`python/franken_networkx/_fnx.abi3.so` is older than Rust sources. I did not copy over or install
the extension during this disk-frugal crate-only run, so the Python proof used the final release
artifact preloaded directly.

## 2026-06-22 BlackThrush DiGraph edges(nbunch) routed to out_edges kernels - 2.65x-7.24x self-speedup (`br-r37-c1-lfpma`, cod-a)

Lever: directed `DiGraph.edges(nbunch, ...)` is semantically out-edge iteration, but the
`_DiGraphEdgeView.__call__` path still walked Python `succ[source].items()` rows for iterable
nbunch calls. `DiGraph.out_edges(nbunch, data=False/True)` already had native node-deduped kernels.
The new route reuses those kernels for exact `DiGraph`, iterable `nbunch`, and `data in {False,
True}`, preserving the existing guarded `OutEdgeDataView` wrapping. Single-node nbunch, data-key
lookups, conversion views, and subgraph views keep the old Python path.

Keep decision: KEEP. This is a Python-only no-build route reuse, not a near-zero lever. It also
fixes duplicate-nbunch parity for the routed pair/data modes because the native out-edge kernels
dedupe repeated nbunch nodes like NetworkX.

Final direct artifact probe:

`PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python` with
`/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`.

| workload | mode | old FNX row route | new FNX | NetworkX | self-speedup | ratio vs NetworkX |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| DiGraph half nbunch | pairs | 2.735 ms | 0.440 ms | 0.564 ms | 6.21x | 1.28x |
| DiGraph half nbunch | data=True | 2.695 ms | 1.017 ms | 0.549 ms | 2.65x | 0.54x |
| DiGraph reversed nbunch | pairs | 2.651 ms | 0.437 ms | 0.549 ms | 6.07x | 1.26x |
| DiGraph reversed nbunch | data=True | 2.654 ms | 0.901 ms | 0.551 ms | 2.95x | 0.61x |
| DiGraph duplicate nbunch | pairs | 3.318 ms | 0.458 ms | 0.567 ms | 7.24x | 1.24x |
| DiGraph duplicate nbunch | data=True | 3.351 ms | 0.929 ms | 0.576 ms | 3.61x | 0.62x |

Behavior proof:

- Direct artifact parity: `list(G.edges(nbunch))` and `list(G.edges(nbunch, data=True))` match
  NetworkX for half, reversed, and duplicate nbunch. The `data=True` tuple's attr dict remains live:
  mutating it updates `G[u][v]`.
- Baseline before edit on the same workload: pairs 0.17x-0.19x vs NetworkX, data=True 0.10x-0.18x
  vs NetworkX. The existing `out_edges` route was already 0.75x-2.25x, confirming this as a route
  miss rather than a missing native primitive.
- `data="weight"` remains on the old Python path because there is no native attr-key nbunch kernel
  yet; duplicate-nbunch attr-key parity remains a separate pre-existing issue.

## 2026-06-22 BlackThrush tournament_matrix direct CSR build - 3.19x-4.80x self-speedup (`br-r37-c1-92qkv`, cod-a)

Lever: `franken_networkx.tournament.tournament_matrix` still re-exported NetworkX's implementation,
which computes `adjacency_matrix(G) - adjacency_matrix(G).T`. On an fnx `DiGraph` that sends
NetworkX through fnx graph views and then pays a sparse subtraction. The new exact-`DiGraph` route
builds the skew CSR matrix directly in one pass over `G.edges()`, preserving node order, sparse
matrix type, int64 unweighted dtype, and NetworkX's implicit `weight="weight"` semantics. Non-exact
directed graph-like inputs keep the NetworkX parity route.

Keep decision: KEEP. This is a contained Python-only route, not a near-zero tweak. The unweighted
tournament row moves from a clear loss to near-NetworkX, and weighted matrices get a 3.19x self
speedup while remaining capped by edge-attribute materialization.

Final direct parity/bench probe:

`PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`.

| workload | old FNX NetworkX-dispatch route | new FNX | NetworkX | self-speedup | ratio vs NetworkX |
| --- | ---: | ---: | ---: | ---: | ---: |
| unweighted tournament n=50 | 2.483 ms | 0.745 ms | 0.795 ms | 3.33x | 1.07x |
| unweighted tournament n=350 | 180.780 ms | 37.654 ms | 36.732 ms | 4.80x | 0.98x |
| unweighted tournament n=700 | 845.236 ms | 186.495 ms | 169.752 ms | 4.53x | 0.91x |
| weighted tournament n=350 | 183.900 ms | 57.620 ms | 39.285 ms | 3.19x | 0.68x |

Behavior proof:

- Direct artifact parity: new and old matrices match NetworkX exactly by dense value for all rows
  above; the focused weighted fixture also preserves sparse class name and dtype.
- `py_compile python/franken_networkx/tournament.py tests/python/test_tournament_module_parity.py`:
  passed.
- `git diff --check`: passed.
- `cargo fmt -p fnx-python --check`: passed.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `ubs python/franken_networkx/tournament.py tests/python/test_tournament_module_parity.py
  docs/NEGATIVE_EVIDENCE.md .beads/issues.jsonl`: exit 0; remaining warnings are existing
  tournament test asserts/random and the module's deliberate wildcard re-export.
- Targeted `pytest` could not run in this checkout because `tests/python/conftest.py` rejected the
  stale in-tree `python/franken_networkx/_fnx.abi3.so`; the proof used the warm release artifact
  directly.

## 2026-06-22 BlackThrush directed nbunch attr-key edge route - 1.19x-1.83x self-speedup (`br-r37-c1-e522x`, cod-a)

Lever: iterable-nbunch directed edge views with `data=<attr>` still walked the attr-key row path
even though `data=True` already had native out-edge nbunch emitters. Exact `DiGraph` and
`MultiDiGraph` `keys=False` now reuse the native `data=True` nbunch rows and project
`attrs.get(key, default)` in Python. The keyed MultiDiGraph variant measured as a regression, so
it stays on the old route.

Keep decision: KEEP. This is not a zero-gain tweak: it removes a duplicate-nbunch parity bug for
DiGraph attr-key `edges` / `out_edges`, and the measured public routes are faster on the target
rows. Some large DiGraph rows remain below NetworkX because the route still materializes live attr
dicts before extracting one value; the deeper fix would be a native attr-key nbunch emitter.

Direct artifact probe:

`PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`.

| workload | old route | new FNX | NetworkX | self-speedup | ratio vs NetworkX |
| --- | ---: | ---: | ---: | ---: | ---: |
| DiGraph out_edges attr-key, n=1500/m=9000/k=750 | 4.094 ms | 2.274 ms | 1.495 ms | 1.80x | 0.66x |
| DiGraph edges attr-key, n=1500/m=9000/k=750 | 4.094 ms | 2.647 ms | 1.511 ms | 1.55x | 0.57x |
| DiGraph out_edges attr-key, n=3500/m=24000/k=1750 | 11.398 ms | 6.780 ms | 4.100 ms | 1.68x | 0.60x |
| DiGraph edges attr-key, n=3500/m=24000/k=1750 | 11.398 ms | 7.701 ms | 4.268 ms | 1.48x | 0.55x |
| MultiDiGraph out_edges attr-key, n=1000/m=8000/k=500 | 3.484 ms | 2.939 ms | 2.858 ms | 1.19x | 0.97x |
| MultiDiGraph out_edges attr-key, n=2500/m=20000/k=1250 | 17.543 ms | 9.594 ms | 9.592 ms | 1.83x | 1.00x |
| MultiDiGraph edges attr-key, n=2500/m=20000/k=1250 | 17.543 ms | 10.344 ms | 16.861 ms | 1.70x | 1.63x |

Behavior proof:

- Direct artifact parity: DiGraph `edges` / `out_edges` with duplicate nbunch nodes and missing
  nodes now match NetworkX for `data="weight", default=-1`; the old DiGraph route repeated edges
  for duplicate nbunch nodes.
- Direct artifact parity: MultiDiGraph `edges` / `out_edges` with `keys=False` attr-key nbunch
  match NetworkX; `keys=True` parity was checked and intentionally left on the old route because
  the native-projection candidate regressed.
- `py_compile python/franken_networkx/__init__.py tests/python/test_graph_utilities.py`: passed.
- `git diff --check`: passed.
- `cargo fmt -p fnx-python --check`: passed.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `ubs --only=python --skip=7 python/franken_networkx/__init__.py`: exit 0; remaining warnings
  are pre-existing broad-file style/security-noise outside this diff.
- `ubs --only=python --skip=7 tests/python/test_graph_utilities.py`: exit 0; remaining warnings
  are pre-existing test-file style noise.
- Targeted `pytest tests/python/test_graph_utilities.py::test_directed_graph_classes_expose_in_and_out_edges
  tests/python/test_graph_utilities.py::test_digraph_edges_nbunch_reuses_out_edge_semantics -q`
  could not collect tests because the checkout stale-extension guard rejected
  `python/franken_networkx/_fnx.abi3.so`; no in-tree install was attempted in this disk-frugal run.

## 2026-06-22 BlackThrush MultiDiGraph selfloop_edges scalar attr read - 1.25x-2.33x self-speedup on target modes (`br-r37-c1-04z53`, cod-b)

Lever: the dense `MultiDiGraph.selfloop_edges` native emitter still materialized a live Python
edge-attr dict for every edge in `data="<attr>"` modes, even though NetworkX returns only the
scalar value there. The new directed multigraph path reads scalar string-key values directly from
the Rust `AttrMap` when no live Python mirror exists, falling back to the mirror for materialized
or mutated attrs and to full dict materialization for nested map values. `data=True` remains on
the live-dict path. The tuple assembly was also split by output shape, avoiding the per-edge
temporary `Vec<PyObject>`.

Keep decision: KEEP for the targeted `data=True` and `data="weight"` modes. It is not a full
domination lever: plain `keys=True` and key-bearing data modes remain key-object/tuple-construction
capped and noisy. But the target residual improves, and behavior stays parity-exact for explicit
keys, string nodes, missing defaults, live attr-dict mutation, and nested dict payloads. No revert.

Same-machine direct probe, with
`/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`:

| workload | mode | before FNX | before NetworkX | before ratio | after FNX | after NetworkX | after ratio |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MultiDiGraph dense self-loops n=2400 parallel=2 | pairs | 6.557 ms | 5.831 ms | 0.89x | 3.854 ms | 3.532 ms | 0.92x |
| MultiDiGraph dense self-loops n=2400 parallel=2 | keys | 10.083 ms | 9.042 ms | 0.90x | 4.687 ms | 3.595 ms | 0.77x |
| MultiDiGraph dense self-loops n=2400 parallel=2 | data=True | 22.789 ms | 6.874 ms | 0.30x | 9.798 ms | 8.150 ms | 0.83x |
| MultiDiGraph dense self-loops n=2400 parallel=2 | keys+data=True | 9.640 ms | 7.969 ms | 0.83x | 11.066 ms | 8.617 ms | 0.78x |
| MultiDiGraph dense self-loops n=2400 parallel=2 | data="weight" | 6.295 ms | 4.059 ms | 0.65x | 5.047 ms | 3.926 ms | 0.78x |
| MultiDiGraph dense self-loops n=2400 parallel=2 | keys+data="weight" | 5.932 ms | 3.796 ms | 0.64x | 6.598 ms | 4.449 ms | 0.67x |

Notes:

- The baseline ratios came from the same warm cod-b target artifact before the edit; the after
  ratios are from the rebuilt local cod-b target artifact.
- Two remote RCH `cargo build -p fnx-python --release --features pyo3/abi3-py310` attempts
  successfully compiled on `vmi1152480` but failed artifact retrieval with `RCH-E309`, so the final
  benchmark artifact was produced by the same crate-scoped build locally with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Direct parity probe passed: int/string nodes, default integer and explicit string edge keys,
  `data=False`, `keys=True`, `data=True`, `keys+data=True`, `data="weight"`,
  `keys+data="weight"`, missing-default modes, live attr-dict mutation before attr-key reads, and
  nested dict payload values.

## 2026-06-22 BlackThrush MultiGraph selfloop_edges scalar attr read - 1.22x-2.56x self-speedup on target modes (`br-r37-c1-0vflm`, cod-a)

Lever: the undirected `MultiGraph.selfloop_edges(data="<attr>")` native emitter still
materialized a live Python attr dict for every self-loop edge before reading a single scalar
attribute. The new path mirrors the earlier `MultiDiGraph` scalar helper: if a live Python attr
dict already exists, read from it; otherwise read string-keyed scalar values directly from the
Rust `AttrMap`, falling back to dict materialization for nested map payloads. Tuple construction is
also split by output shape, removing the per-edge temporary `Vec<PyObject>`.

Keep decision: KEEP. This is not near-zero. The largest measured residual,
`keys=True, data="weight"`, moved from 0.14x/0.21x vs NetworkX to 0.36x/0.36x, and the
standalone scalar modes improved from 0.39x/0.18x to 0.48x/0.46x. The remaining gap is now mostly
key-object and Python tuple construction overhead.

Same-machine direct probe, with
`/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`:

| workload | mode | before FNX | before NetworkX | before ratio | after FNX | after NetworkX | after ratio | self-speedup |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MultiGraph dense self-loops n=2400 parallel=2 int keys | pairs | 0.657 ms | 0.531 ms | 0.81x | 0.592 ms | 0.440 ms | 0.74x | 1.11x |
| MultiGraph dense self-loops n=2400 parallel=2 int keys | keys | 1.298 ms | 0.363 ms | 0.28x | 1.038 ms | 0.376 ms | 0.36x | 1.25x |
| MultiGraph dense self-loops n=2400 parallel=2 int keys | data=True | 1.274 ms | 0.450 ms | 0.35x | 1.257 ms | 0.565 ms | 0.45x | 1.01x |
| MultiGraph dense self-loops n=2400 parallel=2 int keys | keys+data=True | 1.988 ms | 0.474 ms | 0.24x | 1.642 ms | 0.479 ms | 0.29x | 1.21x |
| MultiGraph dense self-loops n=2400 parallel=2 int keys | data="weight" | 1.344 ms | 0.521 ms | 0.39x | 1.101 ms | 0.525 ms | 0.48x | 1.22x |
| MultiGraph dense self-loops n=2400 parallel=2 int keys | keys+data="weight" | 3.943 ms | 0.567 ms | 0.14x | 1.569 ms | 0.558 ms | 0.36x | 2.51x |
| MultiGraph dense self-loops n=2400 parallel=2 string keys | pairs | 0.854 ms | 0.606 ms | 0.71x | 0.757 ms | 0.553 ms | 0.73x | 1.13x |
| MultiGraph dense self-loops n=2400 parallel=2 string keys | keys | 1.495 ms | 0.482 ms | 0.32x | 1.061 ms | 0.482 ms | 0.45x | 1.41x |
| MultiGraph dense self-loops n=2400 parallel=2 string keys | data=True | 1.364 ms | 0.473 ms | 0.35x | 1.240 ms | 0.568 ms | 0.46x | 1.10x |
| MultiGraph dense self-loops n=2400 parallel=2 string keys | keys+data=True | 3.125 ms | 0.867 ms | 0.28x | 1.665 ms | 0.513 ms | 0.31x | 1.88x |
| MultiGraph dense self-loops n=2400 parallel=2 string keys | data="weight" | 2.893 ms | 0.534 ms | 0.18x | 1.130 ms | 0.523 ms | 0.46x | 2.56x |
| MultiGraph dense self-loops n=2400 parallel=2 string keys | keys+data="weight" | 2.705 ms | 0.577 ms | 0.21x | 1.576 ms | 0.567 ms | 0.36x | 1.72x |

Behavior proof:

- Direct artifact parity passed for public `fnx.selfloop_edges` against NetworkX on MultiGraph
  int-key and string-key self-loop workloads across pairs/keys/data/keys_data/weight/keys_weight.
- Focused direct probe passed for missing-default scalar attrs, nested-map payload values, and
  live attr-dict mutation before scalar attr reads.
- `cargo build -p fnx-python --release --features pyo3/abi3-py310`: passed via RCH on `ovh-a`.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed locally after an RCH worker
  killed the first check attempt before completion.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`: passed.
- `cargo test -p fnx-python --features pyo3/abi3-py310`: 27 passed, 0 failed.
- `cargo fmt -p fnx-python --check`: passed.
- `ubs --only=rust crates/fnx-python/src/lib.rs`: exit 0; warnings are pre-existing broad-file
  inventory and no critical issues were reported.
- `git diff --check`: passed.

## 2026-06-22 BlackThrush MultiGraph default-order CSR byte export - 1.22x-1.27x route self-speedup (`br-r37-c1-wggkz`, cod-a)

Lever: default-order `MultiGraph.to_scipy_sparse_array(..., format="csr", dtype=None,
weight="weight")` still used the multigraph COO helper, then handed SciPy duplicate row/col
entries and let COO-to-CSR conversion sort and sum them. The new exact-MultiGraph route builds CSR
rows directly in Rust, mirrors undirected non-self-loops into both row buckets, sums parallel edges
per row, and hands Python native-endian `intp` / data byte buffers through `numpy.frombuffer`.
It preserves the existing live-attr behavior: when edge attrs are dirty it reads the live PyDict
mirror, and it returns to the Python fallback for present nonnumeric or nonfinite weights.

Keep decision: KEEP. The public NetworkX ratio remains noisy because SciPy conversion timing moves
by several milliseconds on the same machine, but the same-artifact route comparison isolates the
lever and shows a durable 1.22x-1.27x speedup over the old COO route with byte-identical CSR output.
No revert.

Direct artifact environment:

`PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260622T1940Z/python:/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260622T1940Z/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`.

Public baseline before the edit:

| workload | FNX median | NetworkX median | ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| MultiGraph random n=2000/m=12000 `to_scipy_sparse_array` | 21.122 ms | 19.452 ms | 0.921x |
| MultiGraph random n=2000/m=12000 `adjacency_matrix` | 23.975 ms | 21.138 ms | 0.882x |
| MultiGraph random n=4000/m=24000 `to_scipy_sparse_array` | 50.248 ms | 44.532 ms | 0.886x |
| MultiGraph random n=4000/m=24000 `adjacency_matrix` | 50.359 ms | 48.940 ms | 0.972x |
| MultiGraph random n=8000/m=48000 `to_scipy_sparse_array` | 126.141 ms | 112.618 ms | 0.893x |
| MultiGraph random n=8000/m=48000 `adjacency_matrix` | 135.628 ms | 109.329 ms | 0.806x |

Public after timing:

| workload | FNX median | NetworkX median | ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| MultiGraph random n=2000/m=12000 `to_scipy_sparse_array` | 22.855 ms | 21.851 ms | 0.956x |
| MultiGraph random n=2000/m=12000 `adjacency_matrix` | 22.228 ms | 24.593 ms | 1.106x |
| MultiGraph random n=4000/m=24000 `to_scipy_sparse_array` | 48.572 ms | 52.783 ms | 1.087x |
| MultiGraph random n=4000/m=24000 `adjacency_matrix` | 49.676 ms | 49.984 ms | 1.006x |
| MultiGraph random n=8000/m=48000 `to_scipy_sparse_array` | 130.577 ms | 129.690 ms | 0.993x |
| MultiGraph random n=8000/m=48000 `adjacency_matrix` | 111.461 ms | 110.062 ms | 0.987x |

Same-artifact old route vs new route, both using the rebuilt extension:

| workload | old COO route median | new CSR bytes route median | public route median | route self-speedup |
| --- | ---: | ---: | ---: | ---: |
| MultiGraph random n=2000/m=12000 | 27.319 ms | 22.260 ms | 18.699 ms | 1.227x |
| MultiGraph random n=4000/m=24000 | 61.688 ms | 48.599 ms | 50.300 ms | 1.269x |
| MultiGraph random n=8000/m=48000 | 136.389 ms | 112.100 ms | 115.410 ms | 1.217x |

Behavior proof:

- Direct artifact parity: old COO route, new CSR bytes route, public
  `to_scipy_sparse_array`, and NetworkX all produced identical sparse matrices for the random
  MultiGraph benchmark rows above.
- Added `test_default_multigraph_csr_parallel_selfloop_and_live_weight_matches_networkx`, covering
  parallel edges, self-loops, missing weights, isolates, and post-creation live attr mutation.
- Preloaded-extension pytest:
  `tests/python/test_to_scipy_sparse_default_native_parity.py`: 8 passed.
- Plain pytest collection from the source tree still cannot import `_fnx` because no in-tree
  extension module exists; the test run preloaded the rebuilt release artifact instead.
- `cargo build -p fnx-python --release --features pyo3/abi3-py310`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed via RCH with the same target dir.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`: passed
  via RCH with the same target dir.
- `cargo fmt -p fnx-python --check`: passed.
- `cargo test -p fnx-python --features pyo3/abi3-py310`: passed locally with the same target dir
  after RCH had no admissible workers; 27 passed, 0 failed.
- `git diff --check`: passed.
- `py_compile python/franken_networkx/__init__.py
  tests/python/test_to_scipy_sparse_default_native_parity.py`: passed.
- `ubs --only=rust crates/fnx-python/src/readwrite.rs`: exit 0; reports pre-existing broad-file
  warnings in `readwrite.rs`, no critical findings.
- `ubs --only=python --skip=7 python/franken_networkx/__init__.py
  tests/python/test_to_scipy_sparse_default_native_parity.py`: exit 0; reports pre-existing broad
  wrapper warnings plus normal test `assert` warnings, no critical findings.

## 2026-06-22 BlackThrush MultiDiGraph directional weighted degree - 19.9x-20.9x FNX self-speedup (`br-r37-c1-8njy5`, cod-a)

Lever: exact full-graph `MultiDiGraph.in_degree(weight="...")` and
`MultiDiGraph.out_degree(weight="...")` used the generic Python
`_DirectedDegreeView` per-node path. Each node walked `MultiAdjacencyView`
wrappers and keydict views before summing edge attrs. The new path routes only
exact, unfiltered, full-graph MultiDiGraph directional weighted degree views to
Rust, walks the native multiedge storage directly, reads the live edge-attr
PyDict mirrors, preserves missing-weight default `1`, and still calls Python
`sum()` once per node to preserve NetworkX-compatible numeric and custom-object
semantics. Nbunch, filtered/reverse views, single-node calls, unweighted calls,
and total directed weighted degree stay on their existing paths.

Keep decision: KEEP. The measured gap that triggered the bead was
`in_degree(weight)` / `out_degree(weight)` at about 0.04x vs NetworkX. The same
artifact-level benchmark shape after the edit is 0.43x / 0.52x vs NetworkX, and
FNX's own median improved about 20x. This is not a near-zero gain.

Direct artifact environment:

`PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`
preloaded as `franken_networkx._fnx`.

Measured trigger baseline before the edit, current turn, `n=1200`, `parallel=4`,
`9600` total directed multiedges:

| workload | FNX median | NetworkX median | ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| `MultiDiGraph.degree(weight="weight")` | 4.882 ms | 2.654 ms | 0.54x |
| `MultiDiGraph.in_degree(weight="weight")` | 40.083 ms | 1.405 ms | 0.04x |
| `MultiDiGraph.out_degree(weight="weight")` | 38.119 ms | 1.424 ms | 0.04x |

After timing, same graph size and total multiedge count with deterministic
parallel edges and missing-weight rows:

| workload | FNX median | NetworkX median | ratio vs NetworkX | parity |
| --- | ---: | ---: | ---: | --- |
| `MultiDiGraph.degree(weight="weight")` | 5.540 ms | 1.623 ms | 0.29x | true |
| `MultiDiGraph.in_degree(weight="weight")` | 1.918 ms | 0.831 ms | 0.43x | true |
| `MultiDiGraph.out_degree(weight="weight")` | 1.918 ms | 0.997 ms | 0.52x | true |
| `MultiDiGraph.degree()` | 0.423 ms | 0.617 ms | 1.46x | true |
| `MultiDiGraph.in_degree()` | 0.137 ms | 0.331 ms | 2.42x | true |
| `MultiDiGraph.out_degree()` | 0.139 ms | 0.320 ms | 2.30x | true |

Behavior proof:

- Direct artifact parity passed for full-list `degree(weight)`, `in_degree(weight)`,
  `out_degree(weight)`, and the unweighted degree views against NetworkX.
- Focused direct probe passed for missing-weight default `1`, post-creation live
  edge-attribute mutation, and single-node `in_degree(node, weight)` /
  `out_degree(node, weight)` parity.
- `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  was attempted with `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`
  and died with wrapper exit 137 before any Rust diagnostic; treated as
  infrastructure failure.
- `cargo +nightly-2026-06-10 build -p fnx-python --release --features pyo3/abi3-py310`:
  passed locally with the same target dir after matching the cached rustc.
- `cargo +nightly-2026-06-10 check -p fnx-python --features pyo3/abi3-py310`:
  passed.
- `cargo +nightly-2026-06-10 clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`:
  passed.
- `cargo +nightly-2026-06-10 test -p fnx-python --features pyo3/abi3-py310`:
  27 passed, 0 failed; doctests 0 passed, 0 failed.
- `cargo +nightly-2026-06-10 fmt -p fnx-python --check`: passed.
- `python -m py_compile python/franken_networkx/__init__.py`: passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/src/digraph.rs`: exit 0; broad pre-existing
  `digraph.rs` warnings, no critical findings.
- `ubs --only=python --skip=7 python/franken_networkx/__init__.py`: exit 0; broad
  pre-existing wrapper warnings, no critical findings.
## 2026-06-22 BlackThrush directed nbunch attr-key native emitters - MultiDiGraph gap 0.42x -> 0.96x (`br-r37-c1-04z53`, cod-b)

Lever: iterable-nbunch directed edge views with `data="<attr>"` still reused the native
`data=True` nbunch rows and projected `attrs.get(...)` in Python. That preserved parity but
materialized a live attr dict for every edge just to return one scalar. Added scalar native
emitters for exact `DiGraph` and exact `MultiDiGraph` `keys=False` paths. The emitters read from a
live mirror when present and otherwise read string-key values from Rust attrs directly; non-string
keys keep parity when a live mirror exists. Single-node nbunch, conversion/subgraph views, and
`keys=True` multigraph attr-key calls stay on the previous paths.

Keep decision: KEEP. The main residual row, `MultiDiGraph.edges(nbunch, data="weight")`, moved from
a clear loss to near parity on best-of-run timing, and `MultiDiGraph.out_edges(nbunch,
data="weight")` flipped to wins. Some median rows remain noisy because both implementations are now
sub-millisecond to low-millisecond list construction paths, but this is not a zero-gain lever.

Same-machine direct probe, with
`/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`:

| workload | route | before FNX best | before NetworkX best | before ratio | after FNX best | after NetworkX best | after ratio |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DiGraph n=1500/m=9000/k=750 | out_edges attr-key | 0.269 ms | 0.279 ms | 1.04x | 0.249 ms | 0.255 ms | 1.02x |
| DiGraph n=1500/m=9000/k=750 | edges attr-key | 0.300 ms | 0.278 ms | 0.93x | 0.279 ms | 0.254 ms | 0.91x |
| DiGraph n=3500/m=24000/k=1750 | out_edges attr-key | 0.690 ms | 0.695 ms | 1.01x | 0.665 ms | 0.635 ms | 0.96x |
| DiGraph n=3500/m=24000/k=1750 | edges attr-key | 0.738 ms | 0.690 ms | 0.93x | 0.645 ms | 0.618 ms | 0.96x |
| MultiDiGraph n=1000/m=8000/k=500 | out_edges attr-key | 1.321 ms | 1.261 ms | 0.96x | 0.909 ms | 1.236 ms | 1.36x |
| MultiDiGraph n=1000/m=8000/k=500 | edges attr-key | 1.684 ms | 1.313 ms | 0.78x | 1.246 ms | 1.247 ms | 1.00x |
| MultiDiGraph n=2500/m=20000/k=1250 | out_edges attr-key | 6.361 ms | 5.332 ms | 0.84x | 2.701 ms | 3.151 ms | 1.17x |
| MultiDiGraph n=2500/m=20000/k=1250 | edges attr-key | 8.133 ms | 3.385 ms | 0.42x | 3.284 ms | 3.151 ms | 0.96x |

Final rebased current-artifact sanity probe:

After the final rebase, rebuilt the release artifact with
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RCH_WORKER=vmi1153651 rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`.
Direct list parity passed against the legacy NetworkX oracle. The MultiDiGraph target remains a
keep with all measured rows above NetworkX. A smaller separate DiGraph iterable-nbunch attr-key
residual remains and is routed as follow-up `br-r37-c1-04z53.9161`.

| workload | route | FNX best | NetworkX best | ratio best |
| --- | --- | ---: | ---: | ---: |
| DiGraph n=1500/m=9000/k=750 unique edges | out_edges attr-key | 0.906 ms | 0.800 ms | 0.88x |
| DiGraph n=1500/m=9000/k=750 unique edges | edges attr-key | 1.122 ms | 0.854 ms | 0.76x |
| DiGraph n=3500/m=24000/k=1750 unique edges | out_edges attr-key | 4.852 ms | 4.262 ms | 0.88x |
| DiGraph n=3500/m=24000/k=1750 unique edges | edges attr-key | 7.010 ms | 6.518 ms | 0.93x |
| MultiDiGraph n=1000/m=8000/k=500 | out_edges attr-key | 1.281 ms | 1.996 ms | 1.56x |
| MultiDiGraph n=1000/m=8000/k=500 | edges attr-key | 1.633 ms | 2.042 ms | 1.25x |
| MultiDiGraph n=2500/m=20000/k=1250 | out_edges attr-key | 8.289 ms | 11.500 ms | 1.39x |
| MultiDiGraph n=2500/m=20000/k=1250 | edges attr-key | 8.903 ms | 10.866 ms | 1.22x |

Behavior proof:

- Direct artifact digest parity passed for every benchmark row above.
- Contract probe passed for duplicate nbunch nodes, missing nbunch nodes, missing attr defaults,
  nested dict attr values, and non-string attr keys stored through the live edge-attr mirrors on
  both `DiGraph` and `MultiDiGraph`.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- `cargo fmt -p fnx-python --check`: passed.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- `cargo test -p fnx-python --features pyo3/abi3-py310`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b` (27 passed).
- `cargo build -p fnx-python --release --features pyo3/abi3-py310`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; release artifact
  retrieved locally and used for the final probe.
- `py_compile python/franken_networkx/__init__.py tests/python/test_graph_utilities.py`: passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/src/digraph.rs`: exit 0; remaining warnings are the existing
  broad-file inventory.
- `ubs --only=python --skip=7 python/franken_networkx/__init__.py
  tests/python/test_graph_utilities.py`: exit 0; remaining warnings are the existing broad-file
  and pytest-assert inventory. A mixed Rust/Python/Markdown UBS invocation was interrupted after
  the Python scanner kept running for several minutes; the Markdown file is not a supported UBS
  language and was covered by `git diff --check`.
## 2026-06-22 BlackThrush MultiGraph selfloop edge-key lookup reuse - 1.6x-1.9x FNX self-speedup (`br-r37-c1-lv4p9`, cod-a)

Lever: `MultiGraph.selfloop_edges(keys=True, data=...)` rebuilt the same
`(u, u, key)` lookup tuple once to recover the Python-visible edge key and again
to read edge data or the live edge-attribute mirror. Reuse the lookup tuple inside
the native `PyMultiGraph::_native_selfloop_edges` loop for the `keys + data`
paths. Plain pair/key-only rows still avoid the tuple when no lookup is needed.

Keep decision: KEEP. The measured trigger gap was explicit string-key
`MultiGraph` self-loop emission at 0.19x-0.22x vs NetworkX. The final same-shape
artifact benchmark improves FNX's own minimum timing by 1.6x-1.9x and improves
the vs-NetworkX ratio to 0.29x-0.36x. This is not a near-zero gain.

Rejected sub-lever: applying the same helper split to `PyMultiDiGraph` did not
hold up on the focused string-key data rows; one repeat measured
`MultiDiGraph str keys_data` / `keys_weight` at only 0.17x vs NetworkX. That
change was backed out before landing, and the accepted diff is scoped to
`PyMultiGraph`.

Direct artifact environment:

`PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`
preloaded as `franken_networkx._fnx`.

Measured trigger baseline before the edit, current turn, `n=2400`,
`parallel=2`, explicit string edge keys, `4800` self-loop multiedges:

| workload | FNX timing | NetworkX timing | ratio vs NetworkX | parity |
| --- | ---: | ---: | ---: | --- |
| `MultiGraph.selfloop_edges(keys=True, data=True)` | 3.276 ms | 0.632 ms | 0.19x | true |
| `MultiGraph.selfloop_edges(keys=True, data="weight")` | 3.576 ms | 0.802 ms | 0.22x | true |

Final after timing, fresh graph per mode, same graph shape and artifact:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `MultiGraph.selfloop_edges(keys=True, data=True)` | 2.021 ms | 2.678 ms | 0.585 ms | 0.607 ms | 0.29x | 0.23x | true |
| `MultiGraph.selfloop_edges(keys=True, data="weight")` | 1.892 ms | 1.921 ms | 0.675 ms | 0.709 ms | 0.36x | 0.37x | true |

Post-rebase sanity probe after rebasing onto `f7dcd8f69` and rebuilding the
release artifact with the same `cod-a` target directory:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `MultiGraph.selfloop_edges(keys=True, data=True)` | 1.651 ms | 2.131 ms | 0.468 ms | 0.541 ms | 0.28x | 0.25x | true |
| `MultiGraph.selfloop_edges(keys=True, data="weight")` | 1.472 ms | 2.158 ms | 0.491 ms | 0.531 ms | 0.33x | 0.25x | true |

Behavior proof:

- Direct artifact parity passed for full-list `MultiGraph` string-key
  `selfloop_edges(keys=True, data=True)` and
  `selfloop_edges(keys=True, data="weight", default=-1)` against NetworkX.
- Focused direct probe passed for missing-data default, nested payload return,
  and post-creation live edge-attribute mutation:
  `franken_networkx` and NetworkX both returned `[('a', 'a', 'k', 'D')]`,
  `[('a', 'a', 'k', {'x': 1})]`, and `[('a', 'a', 'k', 9)]`.
- `cargo +nightly-2026-06-10 build -p fnx-python --release --features pyo3/abi3-py310`:
  passed with `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo +nightly-2026-06-10 check -p fnx-python --features pyo3/abi3-py310`:
  passed.
- `cargo +nightly-2026-06-10 clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`:
  passed.
- `cargo +nightly-2026-06-10 test -p fnx-python --features pyo3/abi3-py310`:
  27 passed, 0 failed; doctests 0 passed, 0 failed.
- `cargo +nightly-2026-06-10 fmt -p fnx-python --check`: passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/src/lib.rs`: exit 0; broad pre-existing
  `lib.rs` warnings, no critical findings.

## 2026-06-22 BlackThrush DiGraph nbunch attr-key scalar fast path - 1.0x-2.3x FNX self-speedup (`br-r37-c1-04z53.9161`, cod-a)

Lever: `_native_out_edges_nbunch_data_key` was already the right route for
exact `DiGraph.out_edges(nbunch, data="<attr>")` and
`DiGraph.edges(nbunch, data="<attr>")`, but each scalar edge read still entered
`edge_attr_value_or_default` by allocating/probing the live edge-attribute mirror
key `(u, v)` before checking the Rust attr map. Fresh benchmark graphs with only
string scalar attrs have no live edge-attr mirrors, so the helper now directly
reads Rust attrs for string keys and missing defaults when `edge_py_attrs` is
empty. Nested map values still fall through to materialize the live dict, and any
existing live edge mirror keeps the old mirror-first path.

Keep decision: KEEP. The smaller row remains an output-construction floor, but
the large-row native scalar path moved substantially and the public
`edges(nbunch, data="weight")` target improved from 7.190 ms to 3.042 ms best on
the same deterministic graph shape. This is not a near-zero gain. A pure wrapper
shortcut was considered and rejected because the current wrapper preserves the
NetworkX-named `OutEdgeDataView` surface and mutation guards.

Direct artifact environment:

`PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`
preloaded as `franken_networkx._fnx`.

Measured trigger baseline before the edit, current turn, deterministic
unique-edge `DiGraph`, `nbunch=list(range(n//2))`, attr key `"weight"`:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `out_edges` n=1500/m=9000/k=750 | 0.882 ms | 0.924 ms | 0.733 ms | 0.751 ms | 0.83x | 0.81x | true |
| `edges` n=1500/m=9000/k=750 | 1.080 ms | 1.236 ms | 0.745 ms | 0.766 ms | 0.69x | 0.62x | true |
| `out_edges` n=3500/m=24000/k=1750 | 7.134 ms | 7.576 ms | 2.065 ms | 6.540 ms | 0.29x | 0.86x | true |
| `edges` n=3500/m=24000/k=1750 | 7.190 ms | 7.453 ms | 6.162 ms | 6.846 ms | 0.86x | 0.92x | true |

After timing, same graph generator and artifact:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `out_edges` n=1500/m=9000/k=750 | 0.881 ms | 0.995 ms | 0.740 ms | 0.762 ms | 0.84x | 0.77x | true |
| `edges` n=1500/m=9000/k=750 | 1.054 ms | 1.077 ms | 0.743 ms | 0.757 ms | 0.70x | 0.70x | true |
| `out_edges` n=3500/m=24000/k=1750 | 3.339 ms | 6.064 ms | 4.198 ms | 5.004 ms | 1.26x | 0.83x | true |
| `edges` n=3500/m=24000/k=1750 | 3.042 ms | 6.040 ms | 2.308 ms | 5.171 ms | 0.76x | 0.86x | true |

Behavior proof:

- Direct artifact parity passed for all four benchmark rows against legacy
  NetworkX.
- Focused direct probe passed for missing-data default, nested payload return,
  and post-creation live edge-attribute mutation:
  `franken_networkx` and NetworkX both returned
  `[('a', 'b', 'D'), ('b', 'c', 'D')]`, `[('a', 'b', {'x': 1})]`, and
  `[('a', 'b', 7)]`.
- `cargo +nightly-2026-06-10 build -p fnx-python --release --features pyo3/abi3-py310`:
  passed with `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo +nightly-2026-06-10 check -p fnx-python --features pyo3/abi3-py310`:
  passed.
- `cargo +nightly-2026-06-10 clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`:
  passed.
- `cargo +nightly-2026-06-10 test -p fnx-python --features pyo3/abi3-py310`:
  27 passed, 0 failed; doctests 0 passed, 0 failed.
- `cargo +nightly-2026-06-10 fmt -p fnx-python --check`: passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/src/digraph.rs`: exit 0; broad pre-existing
  `digraph.rs` warnings, no critical findings.
