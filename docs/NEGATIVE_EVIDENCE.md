# Negative Evidence Ledger

Campaign: `br-r37-c1-04z53` no-gaps performance domination.

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
