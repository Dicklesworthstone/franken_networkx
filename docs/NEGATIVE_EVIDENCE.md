# Negative Evidence Ledger

Campaign: `br-r37-c1-04z53` no-gaps performance domination.

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
| public `fnx.max_weight_matching` delegate | 228.398618 ms | 223.508232 ms | 0.979x | yes | active loss |
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
- Reject/no-ship for this session. The public `max_weight_matching` row remains
  an active `0.979x` loss because exact NetworkX tie-break parity blocks the
  raw native `40x+` route.
- Scorecard accounting for this slice: `0` wins / `1` loss / `0` neutral.

Do not repeat:
- Do not retry endpoint canonicalization, insertion-order node remapping, or
  solver-edge sorting as standalone fixes for this bead. The next viable route
  is a NetworkX-order blossom port/fork that can scan per-vertex adjacency rows
  exactly, or a formally exact uniqueness-gated native dispatch that declines
  tied-optimum cases before public routing.
