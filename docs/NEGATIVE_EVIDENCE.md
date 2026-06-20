# Negative Evidence Ledger

Campaign: `br-r37-c1-04z53` no-gaps performance domination.

Scope for this ledger entry: `br-r37-c1-iyu0a`, multigraph matrix exporters,
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
