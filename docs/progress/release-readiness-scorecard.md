# Release Readiness Scorecard

Target: FrankenNetworkX no-gaps performance gauntlet.

Scope of this update: cut-metric public wrappers from the recent code-first
pending backlog (`br-r37-c1-04z53.9155` and `br-r37-c1-04z53.9153`) plus
sampled edge-betweenness verification (`br-r37-c1-8ox3z.1`) and raw
assortativity verification (`br-r37-c1-04z53.9147`, `.9149`, `.9152`) plus
community link-prediction verification (`br-r37-c1-04z53.9141`) and
undirected `non_edges` default-ebunch verification (`br-r37-c1-04z53.9143`)
plus CCPA link-prediction verification (`br-r37-c1-04z53.9140`) and
MultiDiGraph SCC stale-loss closeout (`br-r37-c1-8hjsu`) plus
MultiDiGraph DAG conversion-tax closeout (`br-r37-c1-11m92`) and
MultiGraph biconnected-family verification plus keyed MST follow-up
(`br-r37-c1-ij951`) and MultiGraph BFS residual closeout
(`br-r37-c1-1jm15`) plus max-weight matching raw-native tie-break
verification (`br-r37-c1-lmqwv`) plus dirty `MultiDiGraph` sparse exporter
boundary verification (`br-r37-c1-kqh2u`) plus cod-b precise dirty-key
dirty sparse-export verification (`br-r37-c1-04z53`) plus cod-a default-order
`MultiDiGraph` CSR row-streaming verification (`br-r37-c1-04z53`) and cod-b
CSR boundary snapshot verification (`br-r37-c1-04z53`) plus
cod-a indexed bytearray CSR boundary verification (`br-r37-c1-q2w4t`) plus
default non-periodic tuple-key lattice generator verification
(`br-r37-c1-ap7at`).

## 2026-06-20 Cod-A Indexed Bytearray CSR Boundary Keep

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260620T2025Z`.
- Requested RCH target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Release extension installed from fresh non-destructive target leaf
  `/data/projects/.rch-targets/franken_networkx-cod-a/f20a-local`; final RCH
  check/test/clippy/build used the requested target with worker-scoped remotes.
- Oracle: vendored NetworkX from this worktree, Python `3.13.7`, pinned source
  `PYTHONPATH`, `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`,
  `OPENBLAS_NUM_THREADS=1`, `taskset -c 4`.

Measured decision:

| Bead | Workload | FNX route | NetworkX | Ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-q2w4t` | n=500, 3k-edge `to_scipy_sparse_array`, default-order MDG | 0.355143 ms | 1.217437 ms | 3.428x | Keep |
| `br-r37-c1-q2w4t` | n=1000, 6k-edge `to_scipy_sparse_array`, default-order MDG | 0.740944 ms | 2.475911 ms | 3.342x | Keep |
| `br-r37-c1-q2w4t` | n=2000, 12k-edge `to_scipy_sparse_array`, default-order MDG | 1.729036 ms | 5.001066 ms | 2.892x | Keep |

Score:
- Target accounting: `3` wins, `0` losses, `0` neutral vs NetworkX.
- Same-process n=2000 fallback comparison: new indexed bytearray CSR path
  `2.3780405 ms`, old list-returning CSR fallback `3.3666895 ms`, NetworkX
  `5.228357 ms`; new path is `1.416x` faster than old and `2.199x` vs
  NetworkX.
- Rejected subattempts: immutable `bytes` buffers failed because SciPy may
  write back during CSR canonicalization; non-indexed `PyByteArray` handoff was
  only a partial self-speedup and stayed below NetworkX in the pinned n=2000
  direct `to_scipy_sparse_array` row.
- Conformance evidence: sparse payload `diff_nnz=0` and sums matched on every
  final sweep row; focused sparse exporter parity `304 passed`; `cargo fmt
  --check`; RCH `cargo check`, `cargo test`, `cargo clippy -D warnings`, and
  `cargo build --release` for `fnx-classes` + `fnx-python` passed.
- UBS completed with exit `0` on the changed Rust files and focused Python
  parity test. The all-touched-file UBS run was stopped after the Python pass
  spent roughly nine minutes on the pre-existing 56k-line public wrapper file;
  focused pytest and `py_compile` are the wrapper-path gates for this slice.
- Ledger hygiene: kept route and rejected subattempts are recorded in
  `docs/NEGATIVE_EVIDENCE.md` and
  `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **keep**. The clean default-order
directed CSR sparse-export residual is closed. Dirty/live sparse exporter rows
remain separate active work.


## 2026-06-20 Cod-B Native Tuple Lattice Generator Keep

Environment:
- Agent Mail identity and CLI actor: `CrimsonRiver`; bead actor: `cod-b`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-20260620T204139Z`.
- Requested RCH target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Local release install against the exact requested target hit incompatible
  rustc E0514 from stale artifacts. No cleanup, deletion, or reset was
  performed. Local installs used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-local-f20a92ec-lattice`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
- Profile: before the final native-position materialization, cProfile showed
  the old fallback spending most wall time in Python batch edge insertion and
  the first native candidate spending the remaining default-row time in Python
  node-position attribute loops.

Measured decision:

| Bead | Workload | Old FNX fallback | Final FNX native | NetworkX | Final ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `br-r37-c1-ap7at` | `triangular_lattice_graph(60, 60)` | 14.366951 ms | 2.859337 ms | 5.038766 ms | 1.762x | keep |
| `br-r37-c1-ap7at` | `hexagonal_lattice_graph(60, 60)` | 40.929678 ms | 11.023525 ms | 14.777368 ms | 1.341x | keep |
| `br-r37-c1-ap7at` | `triangular_lattice_graph(60, 60, with_positions=False)` | 10.185578 ms | 2.063670 ms | 4.104106 ms | 1.989x | keep |
| `br-r37-c1-ap7at` | `hexagonal_lattice_graph(60, 60, with_positions=False)` | 23.653816 ms | 6.158808 ms | 8.533418 ms | 1.386x | keep |

Score:
- Focused accounting: `4` wins, `0` losses, `0` neutral vs NetworkX.
- Rejected subattempt: native structure-only construction still routed default
  position assignment through Python `set_node_attributes`; it measured
  triangular default at only `0.903x` vs NetworkX and hexagonal default at
  `0.698x`, so it was not enough to ship.
- Supplemental RCH Criterion:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head lattice_generators -- --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`
  exited `0` on `vmi1153651`; estimates were triangular `3.584x` and
  hexagonal `1.206x`. Shared-worker outliers make the pinned direct loop the
  keep gate.
- Conformance evidence: focused lattice pytest `24 passed`; per-crate RCH
  `cargo check`, `cargo clippy -D warnings`, `cargo test -p fnx-python`
  (`27 passed`), and release build passed; `cargo fmt --check` and
  `git diff --check` passed.
- Ledger hygiene: control losses, rejected structure-only subattempt, final
  wins, Criterion supplemental rows, and E0514 target-dir caveat are recorded
  in `docs/NEGATIVE_EVIDENCE.md` and
  `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **keep**. Default non-periodic
tuple-key lattice generator construction is no longer an active NetworkX loss.
Do not restore Python tuple-key edge insertion or Python `set_node_attributes`
for this default path; periodic acceleration needs its own parity proof.

## 2026-06-20 Cod-A MultiDiGraph CSR Row-Streaming Reject

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260620T2000`.
- Requested target dir
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a` hit
  incompatible-rustc E0514 (`cc`, `target_lexicon`, `serde`). No cleanup or
  deletion was performed. Candidate/control installs used fresh target
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-boldverify-20260620T2001`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13.7`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.

Measured result:
- Control n=500 `to_scipy MultiDiGraph`: FNX `4.687 ms`, NetworkX
  `3.838 ms`, ratio `0.819x`.
- Candidate n=500 `to_scipy MultiDiGraph`: FNX `4.408 ms`, NetworkX
  `3.927 ms`, ratio `0.891x`, self-speedup `1.063x`, still a loss.
- Control n=2000 `to_scipy MultiDiGraph`: FNX `26.248 ms`, NetworkX
  `21.473 ms`, ratio `0.818x`.
- Candidate n=2000 `to_scipy MultiDiGraph`: FNX `21.973 ms`, NetworkX
  `17.132 ms`, ratio `0.780x`, self-speedup `1.195x`, still a loss.

Outcome:
- Performance evidence: fail as a keep. Score `0` wins / `2` losses /
  `0` neutral against NetworkX. The storage-level row-streaming helper improved
  FNX self-time but did not close the public sparse-export gap.
- Negative evidence: source hunk manually reverted; do not retry row-streaming
  CSR alone. Next route must change the sparse boundary/layout: direct
  NumPy/SciPy buffer handoff, mutation-guarded cached CSR arrays, or a
  caller-specific algorithmic bypass.
- Verification: candidate `rch exec -- cargo check -p fnx-python --features
  pyo3/abi3-py310` passed; reverted-source release install passed from the
  fresh target; focused artifact parity remained `160` configs x `2` exporters,
  `0` fails, golden
  `bff9639b02900c23d43c585672cddf6a3e39676fa40c631efccec93bfeb44307`.

## 2026-06-20 Cod-B MultiDiGraph CSR Boundary Snapshot Reject

Environment:
- Agent Mail identity and CLI actor: `CrimsonRiver`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-20260620T1956`.
- Requested RCH target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Per-crate RCH gates before editing passed:
  `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  and
  `rch exec -- cargo bench -p fnx-python --features pyo3/abi3-py310 --no-run`.
- Local release installs against the exact requested target hit incompatible
  rustc E0514 from stale artifacts. No cleanup, deletion, or reset was
  performed. Candidate installs used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0-csrrow`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
- Fixture: deterministic seed `1`, 2,000 integer nodes, 12,000 keyed random
  edges, 388 public dirty weight mutations, canonical CSR digest
  `f50fd3dec9442adb9b48b2392cf3c63305b314eca3a1e3e3b99f28c63e3d9e36`,
  `11974` canonical nonzeros.
- Profile: 40 calls to the native default-order live finite CSR helper consumed
  `0.563 s` cumulative, about `14 ms` per call.

Measured decision:

| Bead | Workload | FNX route | NetworkX | Ratio vs NetworkX | Candidate vs control | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `br-r37-c1-04z53` | control `to_scipy_sparse_array`, dirty high-unique 12k-edge MDG | 14.974176 ms | 12.004329 ms | 0.802x | baseline | loss |
| `br-r37-c1-04z53` | control `adjacency_matrix`, dirty high-unique 12k-edge MDG | 14.922177 ms | 11.647203 ms | 0.781x | baseline | loss |
| `br-r37-c1-04z53` | source-row stream + Rust dtype flag `to_scipy_sparse_array` candidate | 15.520080 ms | 12.520007 ms | 0.807x | 0.965x self-regression | Reject; loss |
| `br-r37-c1-04z53` | source-row stream + Rust dtype flag `adjacency_matrix` candidate | 13.147295 ms | 11.581038 ms | 0.881x | 1.135x faster | Reject; still loss |
| `br-r37-c1-04z53` | in-call dirty weight snapshot `to_scipy_sparse_array` candidate | 15.587537 ms | 12.611771 ms | 0.809x | 0.961x self-regression | Reject; loss |
| `br-r37-c1-04z53` | in-call dirty weight snapshot `adjacency_matrix` candidate | 15.118008 ms | 12.087389 ms | 0.800x | 0.987x self-regression | Reject; loss |

Score:
- Target accounting: `0` wins, `2` losses, `0` neutral vs NetworkX.
- Candidate 1 improved only the sibling `adjacency_matrix` row and still lost.
  Candidate 2 lost both rows and did not improve the target slice.
- Reverted levers: source-row hashing removal, Python dtype-scan elimination,
  and in-call precise dirty weight snapshot before CSR streaming.
- Conformance evidence: each candidate passed `rch exec -- cargo check -p
  fnx-python --features pyo3/abi3-py310`; each candidate focused sparse parity
  run reported `304 passed`.
- Ledger hygiene: control rows, candidate rows, digest, profile note, E0514
  caveat, and no-repeat guidance are recorded in
  `docs/NEGATIVE_EVIDENCE.md` and
  `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **reject/no-ship**. Leave source on
the control route. Do not retry source-row hashing removal, Python dtype-scan
elimination, or in-call dirty weight snapshot as standalone CSR levers; the
next viable route is a true native sparse-array/CSR buffer boundary or a
compact numeric edge-weight mirror.

## 2026-06-20 Cod-B MultiDiGraph Precise Dirty-Key Sparse Reject

Environment:
- Agent Mail identity and CLI actor: `CrimsonRiver`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-20260620T181919`.
- Requested RCH target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Per-crate RCH release build passed with
  `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`;
  RCH rewrote the target to a worker-scoped cache.
- Local release install against the exact requested target hit
  incompatible-rustc E0514 from stale artifacts. No cleanup, deletion, or reset
  was performed. Candidate and control installs used fresh non-destructive
  target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0-precise`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
- Fixture: deterministic 2,000-node / 12,000-keyed-edge `MultiDiGraph` with
  388 post-construction public dirty weight mutations. Payload digest:
  `558129dd98de2c818c51c16c33e6ec18786afaec48f8d3eddab018c0a24b3cdc`.

Measured decision:

| Bead | Workload | FNX route | NetworkX | Ratio vs NetworkX | Candidate vs control | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `br-r37-c1-04z53` | control `to_scipy_sparse_array`, dirty 12k-edge MDG | 9.680769 ms | 7.469069 ms | 0.772x | baseline | loss |
| `br-r37-c1-04z53` | control `adjacency_matrix`, dirty 12k-edge MDG | 10.238225 ms | 7.189950 ms | 0.702x | baseline | loss |
| `br-r37-c1-04z53` | precise dirty-key `to_scipy_sparse_array` candidate | 7.275282 ms | 6.754456 ms | 0.928x | 1.331x faster | Reject; still loss |
| `br-r37-c1-04z53` | precise dirty-key `adjacency_matrix` candidate | 11.222841 ms | 7.623773 ms | 0.679x | 0.912x regression | Reject; regression |

Score:
- Target accounting: `0` wins, `2` losses, `0` neutral vs NetworkX.
- Self accounting: `1` improvement, `1` regression.
- Reverted lever: when `edge_dirty_keys` was precise, the default-order
  `MultiDiGraph` COO/CSR helpers read stored Rust attrs for untouched edges and
  live Python dicts only for dirty keys. It improved direct
  `to_scipy_sparse_array` but did not beat NetworkX and regressed the sibling
  `adjacency_matrix` public route.
- Conformance evidence: candidate `rch exec -- cargo check -p fnx-python
  --features pyo3/abi3-py310` passed. Final reverted-source gates passed
  `cargo fmt --check`, `git diff --check`, and focused sparse exporter parity
  `304 passed`.
- Ledger hygiene: control rows, candidate rows, digest, E0514 caveat, and next
  route are recorded in `docs/NEGATIVE_EVIDENCE.md` and
  `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **reject/no-ship**. Leave source on
the control route. Do not retry precise dirty-key stored-attr bypass alone; the
next viable route is a true native sparse-array/CSR boundary that removes the
Python/SciPy handoff cost while preserving dtype inference and live attr
semantics.

## 2026-06-20 MultiDiGraph Dirty Sparse Boundary No-Ship

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260620T184133Z`.
- Requested RCH target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Exact requested release install hit incompatible-rustc E0514 in the shared
  target dir; no cleanup or file deletion was performed.
- Release extension and proof runs used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-kqh2u`.
- Oracle: NetworkX `3.6.1`, Python `3.13.7`, same-process release timing,
  `PYTHONHASHSEED=0`, `taskset` core `4`.

Measured decision:

| Bead | Workload | FNX route | NetworkX | Ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-kqh2u` | clean `to_scipy_sparse_array`, default-order n=2000 | 1.390486 ms | 3.557171 ms | 2.558x | Sanity win; not active loss |
| `br-r37-c1-kqh2u` | clean `adjacency_matrix`, default-order n=2000 | 1.518057 ms | 3.632664 ms | 2.393x | Sanity win; not active loss |
| `br-r37-c1-kqh2u` | dirty/live `to_scipy_sparse_array`, 12k-edge MDG baseline | 11.083094 ms | 7.516955 ms | 0.678x | Active loss reproduced |
| `br-r37-c1-kqh2u` | dirty/live `adjacency_matrix`, 12k-edge MDG baseline | 11.440620 ms | 6.928440 ms | 0.606x | Active loss reproduced |
| `br-r37-c1-kqh2u` | dirty/live `to_scipy_sparse_array`, borrowed live-weight index candidate | 14.510345 ms | 6.259952 ms | 0.431x | Reject; regression |
| `br-r37-c1-kqh2u` | dirty/live `adjacency_matrix`, borrowed live-weight index candidate | 9.431321 ms | 5.827642 ms | 0.618x | Reject; still loss |
| `br-r37-c1-kqh2u` | dirty/live `to_scipy_sparse_array`, post-revert release reinstall | 12.386839 ms | 7.455365 ms | 0.602x | Final source still loses |
| `br-r37-c1-kqh2u` | dirty/live `adjacency_matrix`, post-revert release reinstall | 18.037455 ms | 7.471376 ms | 0.414x | Final source still loses |

Score:
- Dirty-boundary candidate accounting: `0` wins, `2` losses, `0` neutral.
- Performance evidence: the clean default-order integer-index sparse exporter
  surface already wins, but dirty/live edge-attribute mirrors still dominate the
  largest `MultiDiGraph` sparse exporter residual.
- Reverted lever: borrowed live-weight pre-indexing avoided owned lookup tuples
  but moved too much live dictionary work up front and regressed the primary
  `to_scipy_sparse_array` target row.
- Conformance evidence: candidate parity digest matched; the candidate passed
  `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`; final
  source was restored and `cargo fmt --check` passed after revert. Post-revert
  release reinstall matched sparse digest
  `c29d2099856ac22e34cb12781f7d70f407c40512ca621cfe74e071c843115c44`.
- Final gates on the reverted source: `git diff --check`,
  `python -m py_compile python/franken_networkx/__init__.py`, focused sparse
  exporter parity `297 passed`,
  `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`,
  and
  `rch exec -- cargo bench -p fnx-python --features pyo3/abi3-py310 --no-run`.
- Ledger hygiene: the clean sanity win, dirty baseline losses, rejected
  candidate losses, E0514 target-dir caveat, and next route are recorded in
  `docs/NEGATIVE_EVIDENCE.md` and
  `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **reject/no-ship**. Keep the residual
open. The next viable route is weight-only dirty-key sync/clear before CSR or a
true native sparse-array boundary for dirty `MultiDiGraph` rows; do not retry
borrowed live-weight pre-indexing as a standalone lever.

## 2026-06-20 Max-Weight Matching No-Ship Slice

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-next-20260620T131825Z`.
- Requested RCH target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Exact requested release install hit incompatible-rustc E0514 in the shared
  target dir; no cleanup or file deletion was performed.
- Release extension and proof runs used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-20260620`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, same-process release timing,
  `PYTHONHASHSEED=0`.

Measured decision:

| Bead | Workload | FNX route | NetworkX | Ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-lmqwv` | public `max_weight_matching`, weighted `gnp(300,0.05,seed=11)` | 228.398618 ms | 223.508232 ms | 0.979x | Active loss; exact delegate |
| `br-r37-c1-lmqwv` | raw `_fnx.max_weight_matching`, same graph | 5.494071 ms | 223.508232 ms | 40.68x | Reject as public route; exact edge set differs |
| `br-r37-c1-lmqwv` | full insertion-order raw variant | 4.954032 ms | 225.624950 ms | 45.54x | Reject; exact drift worsened to `6/20` seeds |
| `br-r37-c1-lmqwv` | insertion-order raw variant with sorted solver edges | 6.292802 ms | 239.127194 ms | 38.00x | Reject; exact drift worsened to `8/20` seeds |

Score:
- Current matching accounting: `0` wins, `1` loss, `0` neutral.
- Performance evidence: raw native blossom is a major speed route, but only as
  routing evidence while exact NetworkX tie-break parity fails.
- Conformance evidence: after reverting both no-ship experiments, focused
  matching tests passed `184` cases:
  `test_matching_conformance.py`,
  `test_max_weight_matching_tuple_direction_parity.py`, and
  `test_flow_cut_matching_value_parity.py`.
- Ledger hygiene: public loss, raw invalid win, both rejected ordering
  variants, E0514 target-dir caveat, and the next viable route are recorded in
  `docs/NEGATIVE_EVIDENCE.md` and
  `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **reject/no-ship**. Do not route the
public wrapper to raw `_fnx.max_weight_matching` until the native solver can
preserve NetworkX's per-vertex adjacency scan order, or until a formal
uniqueness-gated dispatch declines tied-optimum cases.

## 2026-06-20 MultiGraph BFS Follow-Up

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-bfs-20260620T1133Z`.
- Requested RCH target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Exact requested release install hit incompatible-rustc E0514 in the shared
  target dir; no cleanup or file deletion was performed.
- Release extension and RCH gates used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-bfs-f20a92ec0`.
- RCH Criterion final command:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head -- bfs_edges_mg1000_e5000 --noplot`.

Measured decision:

| Bead | Workload | Baseline ratio | Final ratio | Decision |
| --- | --- | ---: | ---: | --- |
| `br-r37-c1-1jm15` | `bfs_edges(source=0)`, MultiGraph 1000 nodes / 5000 edges | `0.730x` clean-worktree release loop; prior `ij951` sweep `0.825x` | `1.098x` same-process release loop; `1.243x` RCH Criterion | Keep; loss flipped |

Score:
- Current BFS accounting: `1` win, `0` losses, `0` neutral.
- Performance evidence: borrowed `MultiGraph::neighbors_iter` plus direct
  borrowed row BFS removes full indexed adjacency rebuild and endpoint string
  clones while preserving NetworkX discovery/display order.
- Conformance evidence: focused traversal parity `204 passed`; broader
  BFS/traversal parity `136 passed`; Rust `fnx-classes` tests `68 passed,
  2 ignored`.
- Build evidence: `cargo fmt --check`, `rch exec -- cargo check -p fnx-python
  --features pyo3/abi3-py310`, and `rch exec -- cargo clippy -p fnx-python
  --all-targets --features pyo3/abi3-py310 -- -D warnings` passed.
- Ledger hygiene: the baseline loss, final win, E0514 target-dir caveat, and
  unrelated Dijkstra follow-up `br-r37-c1-syrw5` are recorded in
  `docs/NEGATIVE_EVIDENCE.md` and `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **keep BFS follow-up; active
MultiGraph BFS residual closed**.

## 2026-06-20 MultiGraph Keyed MST Follow-Up

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-a`.
- Worktree: `/data/projects/franken_networkx`.
- Requested RCH target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Exact requested local release install hit incompatible-rustc E0514 in the
  shared target dir; no cleanup or file deletion was performed.
- Release extension for local Python timing used fresh target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-mst`.
- Exact-target RCH release build passed:
  `rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`.
- Exact-target bench first fell back locally because no RCH workers were
  admissible and hit shared-target E0514; the measured Criterion bench used the
  fresh target dir without deleting shared artifacts.

Measured decision:

| Bead | Workload | Baseline ratio | Final ratio | Decision |
| --- | --- | ---: | ---: | --- |
| `br-r37-c1-ij951` | `minimum_spanning_tree`, MultiGraph 1000 nodes / 5000 edges | `0.313x` old parity route | `1.124x` pinned release sweep; `1.214x` Criterion | Keep; loss flipped |
| `br-r37-c1-ij951` side surface | `is_biconnected` | previous keep | `6.801x` current pinned sweep; `10.454x` Criterion | Win |
| `br-r37-c1-ij951` side surface | `articulation_points` | previous keep | `4.868x` current pinned sweep; `6.401x` Criterion | Win |
| `br-r37-c1-ij951` side surface | `biconnected_components` | previous keep | `2.839x` current pinned sweep; `4.065x` Criterion | Win |
| `br-r37-c1-ij951` residual | `bfs_edges(source=0)` | `0.407x` prior baseline | `0.825x` current pinned sweep | Historical loss; split to `br-r37-c1-1jm15` and closed above |

Score:
- Current pinned `ij951` accounting: `4` wins, `1` loss, `0` neutral; including
  the previously measured `biconnected_component_edges` side row gives
  `5` wins, `1` loss, `0` neutral.
- Performance evidence: native PyO3 keyed MultiGraph MST avoids
  `_networkx_graph_for_parity`, scans edge snapshots directly, runs stable
  Kruskal union-find, and returns a real `MultiGraph` with selected keys and
  attrs preserved.
- Conformance evidence: MST regression file `55 passed`; tree/bipartite
  `63 passed`; parity conformance `195 passed`; Rust `fnx-python` tests
  `27 passed`.
- Ledger hygiene: the old parity loss, native keep, exact-target E0514 bench
  caveat, and residual BFS loss are recorded in `docs/NEGATIVE_EVIDENCE.md`
  and `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **keep MST follow-up**. The residual
BFS row was split out and closed by `br-r37-c1-1jm15` above.

## 2026-06-20 MultiDiGraph DAG Closeout

Environment:
- Agent: `CrimsonRiver` / `cod-a`.
- Worktree: `/data/projects/franken_networkx-cod-a-land`.
- Requested RCH target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Exact requested local release install hit incompatible-rustc E0514 in the
  shared target dir; no cleanup or file deletion was performed.
- Release extension rebuilt with fresh target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-local-f20a92ec0`.
- Harness: same-process release timing against NetworkX `3.6.1`,
  `PYTHONHASHSEED=0`, identical deterministic 420-node / 1329-edge
  parallel-keyed `MultiDiGraph` DAG with digest parity on every row.

Measured release medians:

| Bead | Workload | Baseline Ratio | Final FNX | Final NetworkX | Final Ratio | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `br-r37-c1-11m92` | `topological_sort` | 5.824x | 0.197824 ms | 1.052203 ms | 5.319x | Win |
| `br-r37-c1-11m92` | `dag_longest_path` | 1.532x | 1.330331 ms | 2.036158 ms | 1.531x | Win |
| `br-r37-c1-11m92` | `dag_longest_path_length` | 0.699x | 1.303539 ms | 2.718360 ms | 2.085x | Keep; loss flipped |
| `br-r37-c1-11m92` | `transitive_closure` | 0.567x | 265.605101 ms | 627.405576 ms | 2.362x | Keep; loss flipped |
| `br-r37-c1-11m92` | `number_strongly_connected_components` | 3.399x | 0.116190 ms | 0.356205 ms | 3.066x | Win |

Kept levers:
- Native `MultiDiGraph` `transitive_closure(reflexive=False)` distinct-successor
  reachability plus bulk keyed-edge insertion. Row-key override mirrors still
  use the fallback path.
- Direct directed-multigraph `dag_longest_path_length` dynamic-program length
  emission, avoiding full path materialization and Python multiedge re-indexing.

Score:
- Win/loss/neutral accounting: `5` wins, `0` losses, `0` neutral for the final
  DAG surface.
- Self-speedups: `transitive_closure` `4.383x`; `dag_longest_path_length`
  `3.383x`.
- Gates: `cargo fmt --check`; `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`;
  `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`;
  `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`;
  `rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310` (`27 passed`);
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head multidigraph_connectivity_head_to_head -- --noplot`
  exit `0` on `vmi1149989` with no Criterion timing rows retrieved for this
  DAG surface; focused DAG/closure/parity pytest `230 passed`.
- Ledger hygiene: the baseline losses, final wins, E0514 target-dir note, and
  no-repeat guidance are recorded in `docs/NEGATIVE_EVIDENCE.md` and
  `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **keep/stale-loss closed**. Do not
retry Python edge-by-edge transitive closure or full-path materialization for
directed-multigraph longest-path length; route effort to still-losing measured
surfaces.

## 2026-06-20 MultiGraph Biconnected Family BOLD-VERIFY Slice

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-b`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-ij951-boldverify-20260620T061230Z`.
- Target dir requested for RCH:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Release install used fresh target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0` after the shared
  target dir hit incompatible-rustc E0514; no cleanup was performed.
- RCH Criterion:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head multigraph_biconnected -- --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`
  on `hz1`.
- RCH release build:
  `rch exec -- cargo build -p fnx-python --release` on `vmi1153651`.
- Clippy:
  `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings` completed
  green via local fallback after rch remote sync timeout.
- Focused conformance:
  `tests/python/test_multigraph_algorithms.py`,
  `test_matching_flow_cross_type.py::test_is_biconnected_nx`, and
  `test_parity_conformance.py -k biconnected` passed with
  `8 passed, 235 deselected`.

Baseline and final decision:

| Bead | Workload | Baseline ratio | Final ratio | Decision |
| --- | --- | ---: | ---: | --- |
| `br-r37-c1-ij951` | `is_biconnected`, MultiGraph 1000 nodes / 5000 edges | `0.230x` | `10.584x` RCH Criterion | Keep |
| `br-r37-c1-ij951` | `articulation_points`, same fixture | `0.103x` | `6.553x` RCH Criterion | Keep |
| `br-r37-c1-ij951` | `biconnected_components`, same fixture | `0.196x` | `3.619x` RCH Criterion | Keep |
| `br-r37-c1-ij951` side surface | `biconnected_component_edges`, same fixture | n/a | `1.396x` direct release sweep | Keep |
| `br-r37-c1-ij951` residual | `minimum_spanning_tree`, same fixture | `0.320x` | `0.296x` direct release sweep | Historical loss; closed by keyed MST follow-up |
| `br-r37-c1-ij951` residual | `bfs_edges(source=0)`, same fixture | `0.407x` | `0.399x` direct release sweep | Historical loss; closed by BFS follow-up |

Score:
- Win/loss/neutral accounting: `4` wins, `2` losses, `0` neutral on the
  expanded MultiGraph biconnected/MST/BFS surface.
- Performance evidence: direct ordered-adjacency MultiGraph biconnected kernels
  remove simple-Graph materialization and NetworkX delegation while preserving
  row order and component-edge orientation.
- Conformance evidence: focused biconnected/MultiGraph parity is green.
- Ledger hygiene: both wins and residual losses are recorded in
  `docs/NEGATIVE_EVIDENCE.md` and `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **conditional pass for MultiGraph
biconnected-family queries**. The historical MST/BFS residuals are closed by
the follow-up sections above.

## 2026-06-20 MultiDiGraph SCC Stale-Loss Closeout

Environment:
- Agent: `CrimsonRiver` / `cod-b`.
- Worktree: `/data/projects/.scratch/franken_networkx-cod-b-scc-boldverify-20260620`.
- Baseline/current source: `origin/main` at `cdf8d86d8`.
- Requested target dir: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Exact requested release install failed with incompatible-rustc E0514 because
  the shared target dir contained older nightly artifacts; no cleanup or file
  deletion was performed.
- Release extension rebuilt with `rch exec -- maturin develop --release --features pyo3/abi3-py310`
  using fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0-scc`.
- Per-crate RCH bench/build gate completed on `vmi1152480`:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head multidigraph_connectivity_head_to_head -- --noplot`.
  The retrieved transcript omitted Criterion timing rows, so the release ratio
  gate used the same-process Python head-to-head harness below.
- Focused conformance:
  `tests/python/test_strongly_connected_components_order_parity.py`,
  `test_directed_multigraph_degenerate_parity.py::test_multidigraph_strongly_connected_components_matches_networkx`,
  `tests/python/test_scc_condensation_invariants.py`, and
  `test_networkx_interop_directed_multi.py::test_multidigraph_interop` passed
  with `212 passed in 1.01s`.

Measured same-process release head-to-head on an identical 1800-node
block/parallel-arc `MultiDiGraph` with block size `6`:

| Bead | Workload | FNX median | NetworkX median | Ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-8hjsu` | `strongly_connected_components` | 0.642898 ms | 1.717424 ms | 2.671x | Keep current route; close stale loss |
| `br-r37-c1-8hjsu` side surface | `number_strongly_connected_components` | 0.338000 ms | 1.542392 ms | 4.563x | Win |
| `br-r37-c1-8hjsu` side surface | `descendants(source=0)` | 0.457607 ms | 0.750663 ms | 1.640x | Win |

Score:
- Win/loss/neutral accounting: `1` win, `0` losses, `0` neutral for the SCC
  bead row; `3` wins, `0` losses, `0` neutral for the measured SCC/count/desc
  side surface.
- Performance evidence: the current native direct successor-row SCC route beats
  NetworkX on the open-loss fixture; no new code was needed.
- Conformance evidence: focused SCC/condensation/interop parity is green.
- Ledger hygiene: the no-code closeout, E0514 target-dir issue, and no-repeat
  notes are recorded in `docs/NEGATIVE_EVIDENCE.md` and
  `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **pass/stale-loss closed**. Do not
spend another lever on MultiDiGraph SCC until a fresh head-to-head row shows a
real loss; route effort to remaining measured losses instead.

## 2026-06-20 MultiDiGraph Reverse Copy BOLD-VERIFY Slice

Environment:
- Agent: `CrimsonRiver` / `cod-a`.
- Target dirs:
  `/data/projects/.rch-targets/franken_networkx-cod-a-local-check` for local
  release install and
  `/data/projects/.rch-targets/franken_networkx-cod-a-reverify-f20a` for RCH
  release build verification.
- Harness: direct `MultiDiGraph.reverse(copy=True)` loop, 300 nodes, 2936 keyed
  edges, weighted/tagged attrs, dirty variant mutating every 31st edge.
- Runtime: Python `3.13.7`, NetworkX `3.6.1`, `PYTHONHASHSEED=0`, core pinned
  with `taskset -c 4`, 31 timed runs after 8 warmups.

Final measured medians:

| Bead | Workload | FNX median | NetworkX median | Ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-nooou` | clean keyed attrs | 7.348492 ms | 9.740804 ms | 1.326x | Keep |
| `br-r37-c1-nooou` | dirty post attrs | 7.264913 ms | 9.253100 ms | 1.274x | Keep |

Post-rebase smoke after clean-tree release install:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Digest |
| --- | ---: | ---: | ---: | --- |
| clean keyed attrs | 4.980806 ms | 8.641853 ms | 1.735x | `5987af29b718da04` |
| dirty post attrs | 5.853450 ms | 9.164683 ms | 1.566x | `1d35fe579cedf7b5` |

Rejected subattempt:
- Sparse keyed-edge dirty tracking without lazy edge-attr mirror materialization
  still lost on dirty attrs: `13.222951 ms` vs NetworkX `10.718466 ms`
  (`0.811x`). The final kept lever adds lazy mirror materialization for
  lossless scalar/string-keyed attr dicts while still copying dirty or
  non-lossless Python mirrors.

Score:
- Win/loss/neutral accounting: `2` wins, `0` losses, `0` neutral for the final
  clean and dirty reverse-copy workloads.
- Performance evidence: dirty reverse-copy mirror loss moved from `0.849x` to
  `1.274x`; clean keyed attrs improved from `1.177x` to `1.326x`.
- Focused conformance: reverse/adjacency/dirty-attr parity `53 passed`; clean
  hash64 `7657081794215802141`, dirty hash64 `7376594841975813130`.
- Gates: `cargo fmt --check`; `cargo check -p fnx-python --benches`;
  `cargo clippy -p fnx-python --all-targets -- -D warnings`;
  `rch exec -- cargo build --release -p fnx-python`; `ubs` on touched files.

Release readiness verdict for this slice: **keep**. Do not repeat the
sparse-only dirty-key attempt as a standalone lever; it was measured and
rejected.

## 2026-06-20 MultiDiGraph Weighted Sparse Export Live-Dict Slice

Environment:
- Agent: `CrimsonRiver` / `cod-b`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-wvuf7-20260620T1045Z`.
- Target dir: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Release extension rebuilt with `maturin develop --release --features pyo3/abi3-py310`
  using fresh target dir `/data/projects/.rch-targets/franken_networkx-cod-b-maturin-f20a`
  after the shared target dir hit incompatible-rustc E0514. No cleanup or file
  deletion was performed.
- Harness: same-process release Python timing against vendored NetworkX
  `3.7rc0.dev0`, public weighted graph construction, and parity checks before
  every timing row.
- Gates: `cargo fmt --check`; `rch exec -- cargo check -p fnx-python --benches`;
  `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`;
  `rch exec -- cargo build -p fnx-python --release`; focused sparse-export
  parity `297 passed`; sparse plus numpy weighted exporter parity `305 passed`.

Final accepted medians after narrowing the live-dict route to `MultiDiGraph`:

| Bead | Workload | FNX median | NetworkX median | Ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-wvuf7` | `MultiGraph n=250 to_scipy_sparse_array` | 0.637 ms | 0.779 ms | 1.224x | Win |
| `br-r37-c1-wvuf7` | `MultiGraph n=250 adjacency_matrix` | 0.684 ms | 0.800 ms | 1.170x | Win |
| `br-r37-c1-wvuf7` | `MultiGraph n=1000 to_scipy_sparse_array` | 2.576 ms | 3.114 ms | 1.209x | Win |
| `br-r37-c1-wvuf7` | `MultiGraph n=1000 adjacency_matrix` | 3.283 ms | 3.835 ms | 1.168x | Win |
| `br-r37-c1-wvuf7` | `MultiGraph n=2000 to_scipy_sparse_array` | 7.559 ms | 8.444 ms | 1.117x | Win |
| `br-r37-c1-wvuf7` | `MultiGraph n=2000 adjacency_matrix` | 7.823 ms | 6.312 ms | 0.807x | Loss |
| `br-r37-c1-wvuf7` | `MultiDiGraph n=250 to_scipy_sparse_array` | 0.489 ms | 0.545 ms | 1.113x | Win |
| `br-r37-c1-wvuf7` | `MultiDiGraph n=250 adjacency_matrix` | 0.494 ms | 0.553 ms | 1.119x | Win |
| `br-r37-c1-wvuf7` | `MultiDiGraph n=1000 to_scipy_sparse_array` | 1.946 ms | 2.190 ms | 1.125x | Win |
| `br-r37-c1-wvuf7` | `MultiDiGraph n=1000 adjacency_matrix` | 2.013 ms | 2.724 ms | 1.353x | Win |
| `br-r37-c1-wvuf7` | `MultiDiGraph n=2000 to_scipy_sparse_array` | 8.707 ms | 6.324 ms | 0.726x | Loss |
| `br-r37-c1-wvuf7` | `MultiDiGraph n=2000 adjacency_matrix` | 11.363 ms | 8.008 ms | 0.705x | Loss |

Focused largest directed repeat:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Decision |
| --- | ---: | ---: | ---: | --- |
| `MultiDiGraph n=2000 to_scipy_sparse_array` | 7.838 ms | 5.392 ms | 0.688x | Residual loss |
| `MultiDiGraph n=2000 adjacency_matrix` | 9.171 ms | 5.652 ms | 0.616x | Residual loss |

Rejected subattempt:
- Routing the live-dict helper for both `MultiGraph` and `MultiDiGraph`
  regressed measured `MultiGraph` rows (`0.750x`, `0.663x`, `0.638x`,
  `0.608x` on representative exporter rows), so the final code keeps
  `MultiGraph` on the existing checked native sync path.

Score:
- Win/loss/neutral accounting: `9` wins, `3` losses, `0` neutral for the final
  expanded slice; the target largest directed rows remain `0` wins, `2` losses
  on focused repeat.
- Performance evidence: target `MultiDiGraph n=2000 to_scipy_sparse_array`
  moved from `17.289 ms` to `8.707 ms` in the expanded sweep (`1.985x` FNX
  self-speedup), and `adjacency_matrix` moved from `14.045 ms` to `11.363 ms`
  (`1.236x` self-speedup). Focused repeat improves those self-speedups to
  `2.206x` and `1.531x`, but NetworkX is still faster.
- Ledger hygiene: baseline, accepted route, rejected all-multigraph route, and
  residual n=2000 losses are recorded in `docs/NEGATIVE_EVIDENCE.md` and
  `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **partial keep / not dominated**. The
live-dict route is worth keeping for directed multigraph exporter sync removal,
but this bead stays open for a default-order integer-index COO/boundary
specialization.

## 2026-06-20 Default-Order Multigraph Matrix Exporter BOLD-VERIFY Slice

Environment:
- Agent: `CrimsonRiver` / `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-bold-20260620T1345`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- The requested shared target hit incompatible-rustc E0514 and was not
  cleaned. Release proof used fresh target
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-iyu0a-20260620T1349`.
- Post-rebase release install used second fresh target
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-iyu0a-postrebase-20260620T1832`
  after the first fresh target also hit E0514. No target cleanup was performed.
- Gates: `cargo fmt --check`; `git diff --check`;
  `python3 -m py_compile python/franken_networkx/__init__.py`;
  `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`;
  `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`;
  `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`;
  `rch exec -- cargo bench -p fnx-python --features pyo3/abi3-py310 --no-run`;
  release `maturin develop --release --features pyo3/abi3-py310`;
  focused exporter pytest `604 passed` before and after rebase.
- Harness: `tests/artifacts/perf/20260620T-multigraph-matrix-coo-cc/bench_and_parity.py`.
- Focused conformance: final run reported `160` configs x `2` exporters,
  `0` fails, golden `bff9639b02900c23d43c585672cddf6a3e39676fa40c631efccec93bfeb44307`.

Kept route:
- Native default-order multigraph COO helper for `nodelist=None`, avoiding
  Python nodelist canonicalization and reading stored attrs directly when
  `edges_dirty` is false.
- `MultiDiGraph` default CSR helper for `format="csr"` that pre-sums parallel
  edge buckets before SciPy construction.

Final artifact harness:

| Bead | Workload | FNX | NetworkX | Ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-iyu0a` | n=500 `to_numpy_array`, `MultiGraph` | 1.76 ms | 2.38 ms | 1.352x | Win |
| `br-r37-c1-iyu0a` | n=500 `to_scipy_sparse_array`, `MultiGraph` | 1.89 ms | 2.18 ms | 1.155x | Win |
| `br-r37-c1-iyu0a` | n=500 `to_numpy_array`, `MultiDiGraph` | 2.43 ms | 4.23 ms | 1.741x | Win |
| `br-r37-c1-iyu0a` | n=500 `to_scipy_sparse_array`, `MultiDiGraph` | 1.99 ms | 3.00 ms | 1.508x | Win |

Large residual probe:

| Workload | FNX | NetworkX | Ratio vs NetworkX | Decision |
| --- | ---: | ---: | ---: | --- |
| n=2000 `to_numpy MultiGraph` | 8.199 ms | 7.888 ms | 0.962x | Residual loss |
| n=2000 `to_scipy MultiGraph` | 6.004 ms | 5.007 ms | 0.834x | Residual loss |
| n=2000 `to_numpy MultiDiGraph` | 11.797 ms | 13.844 ms | 1.174x | Win |
| n=2000 `to_scipy MultiDiGraph`, min-of-9 | 8.097 ms | 7.005 ms | 0.865x | Residual loss |
| n=2000 `to_scipy MultiDiGraph`, 50-run min | 5.790 ms | 6.793 ms | 1.173x | Noisy win |
| n=2000 `to_scipy MultiDiGraph`, 50-run median | 9.290 ms | 8.276 ms | 0.891x | Residual loss |

Rejected subattempts:
- Broad undirected default-order dispatch regressed large `MultiGraph`
  `to_scipy_sparse_array` (`0.777x`) and was narrowed away.
- Streaming-successor CSR accessors regressed the n=500 fixture
  (`to_scipy MultiDiGraph` `0.808x`) and were manually reverted.

Score:
- Win/loss/neutral accounting for original n≈400/500 exporter gap:
  `4` wins, `0` losses, `0` neutral.
- Performance evidence: large sparse median rows are improved but not dominated.
- Ledger hygiene: kept route, residual losses, and reverted subattempts are
  recorded in `docs/NEGATIVE_EVIDENCE.md` and
  `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **partial keep**. Close the original
default-order exporter gap, but keep a follow-up for large sparse multigraph
matrix exporter boundary/layout work.

## 2026-06-19 MultiDiGraph Connectivity BOLD-VERIFY Slice

Environment:
- Agent: `CrimsonRiver` / `cod-b`.
- Target dir: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Release extension rebuilt with `maturin develop --release --features pyo3/abi3-py310`.
- RCH Criterion worker: `vmi1227854`.
- Compile gate: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --benches` passed.
- Focused conformance:
  - `tests/python/test_directed_multigraph_degenerate_parity.py tests/python/test_strongly_connected_conformance.py -q` passed with `391 passed in 0.97s`.
  - `tests/python/test_directed_multigraph_degenerate_parity.py tests/python/test_traversal.py tests/python/test_multigraph_algorithms.py -q` passed with `187 passed in 0.84s`.
  - Relevant dicsr traversal checks passed with `2 passed in 0.45s`.
- Broad conformance note: full `test_dicsr_cache_parity.py` currently has an unrelated pre-existing `test_multi_source_dijkstra_directed_finalize_order` failure; this route does not touch multi-source Dijkstra.
- Formatting note: workspace `cargo fmt --check` is currently blocked by pre-existing rustfmt drift in shared files, including `crates/fnx-algorithms/src/lib.rs`; no workspace formatter was run over peer-owned changes.

| Bead | Workload | FNX mean | NetworkX mean | FNX speedup | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-zid1b` | `strongly_connected_components`, MultiDiGraph 1800 nodes, block size 6, parallel arcs | 925.39 us | 2.2594 ms | 2.44x | Keep |
| `br-r37-c1-zid1b` | `descendants`, same MultiDiGraph, source `0` | 579.76 us | 1.0212 ms | 1.76x | Keep |

Surface sweep after both routes, same 1800-node MultiDiGraph shape:

| Function | Ratio vs NetworkX | Decision |
| --- | ---: | --- |
| `single_source_shortest_path_length` | 1.29x | Win |
| `shortest_path_length` | 2.85x | Win |
| `has_path` | 3.08x | Win |
| `weakly_connected_components` | 1.02x | Neutral |
| `number_weakly_connected_components` | 1.31x | Win |
| `is_weakly_connected` | 1.68x | Win |
| `strongly_connected_components` | 2.27x local probe; 2.44x RCH Criterion | Keep |
| `number_strongly_connected_components` | 4.53x | Win |
| `is_strongly_connected` | 1.23x | Win |
| `descendants` | 1.45x local probe; 1.76x RCH Criterion | Keep |

Score:
- Win/loss/neutral accounting: `9` wins, `1` neutral, `0` losses on the sampled
  MultiDiGraph reachability/connectivity surface.
- Performance evidence: `strongly_connected_components(MultiDiGraph)` and
  `descendants(MultiDiGraph, source)` now have same-worker RCH Criterion keep
  rows and reusable benchmark rows in `networkx_head_to_head`.
- Conformance evidence: focused directed/MultiDiGraph SCC, traversal, and
  adjacency-row discovery conformance is green.
- Ledger hygiene: keeps and the remaining neutral weak-component row are recorded in
  `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **conditional pass for
MultiDiGraph connectivity/reachability**. The sampled surface has no remaining
losses; only `weakly_connected_components` is neutral rather than a decisive
win.

## 2026-06-20 BOLD-VERIFY Node Expansion + Node-Degree XY Closeout

Environment:
- Agent: `CrimsonRiver` / `cod-b`.
- Worktree: `/data/projects/.scratch/franken_networkx-cod-b-20260620T1318`.
- Requested target dir: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- RCH note: the exact requested target dir hit incompatible-rustc E0514 from
  older artifacts. No cleanup, deletion, or reset was performed. Release and
  benchmark proof used fresh target
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0-1318`.
- Release extension rebuilt with
  `rch exec -- maturin develop --release --features pyo3/abi3-py310`.

| Bead | Workload | FNX median | NetworkX median | FNX speedup | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-04z53` | `node_expansion`, BA2500/S1250 baseline, RCH Criterion on `vmi1149989` | 1.7826 ms | 629.01 us | 0.353x | Loss confirmed |
| `br-r37-c1-04z53` | `node_expansion`, WS2500/S625 baseline, RCH Criterion on `vmi1149989` | 776.82 us | 380.16 us | 0.489x | Loss confirmed |
| `br-r37-c1-04z53` | `node_expansion`, BA2500/S1250 after Rust validate+bitmap public route, RCH Criterion on `vmi1152480` | 213.68 us | 527.47 us | 2.469x | Keep |
| `br-r37-c1-04z53` | `node_expansion`, WS2500/S625 after Rust validate+bitmap public route, RCH Criterion on `vmi1152480` | 94.674 us | 292.24 us | 3.087x | Keep |
| `br-r37-c1-04z53` | public `fnx.node_degree_xy`, h512/s32, fresh RCH rebaseline on `vmi1153651` | 116.87 ms | 336.80 ms | 2.882x | Stale loss closed |
| `br-r37-c1-04z53` | public directed `fnx.node_degree_xy`, l512/f32, fresh RCH rebaseline on `vmi1153651` | 158.65 ms | 336.86 ms | 2.123x | Stale loss closed |
| `br-r37-c1-04z53` | raw `_fnx.node_degree_xy_rust`, h512/s32, same RCH rebaseline | 29.948 ms | 362.97 ms | 12.120x | Valid side win |
| `br-r37-c1-04z53` | raw directed `_fnx.node_degree_xy_rust`, l512/f32, same RCH rebaseline | 38.594 ms | 443.04 ms | 11.479x | Valid side win |

Score:
- Win/loss/neutral accounting: `4` public wins, `0` active public losses,
  `0` neutral for the current pass; raw side evidence adds `2` valid wins.
- Conformance evidence: focused graph-metrics expansion route passed
  `55` tests; focused graph-metrics expansion + conformance passed `199`
  tests; `fnx-python` Rust tests reported `27 passed`; `cargo fmt --check`,
  per-crate `fnx-python` check, and per-crate `fnx-python` clippy passed.
  UBS completed on the Rust binding file and the focused Python test file; the
  large public `python/franken_networkx/__init__.py` Python-only UBS pass timed
  out after `300s`, with `py_compile`, focused pytest, and Criterion parity
  used as the Python public-wrapper gates.
  The Criterion harness asserts `node_expansion` and
  `node_degree_xy` parity before timing. Missing-node `node_expansion`
  still raises `NetworkXError("The node 99 is not in the graph.")`.
- Ledger hygiene: baseline losses, final wins, `node_degree_xy` stale-loss
  closeout, and the target-dir E0514 caveat are recorded in
  `docs/NEGATIVE_EVIDENCE.md`.

Release readiness verdict for this slice: **keep/stale-loss closed**.
`node_expansion` is no longer an active loss; `node_degree_xy` should not be
reworked again without a fresh head-to-head row showing a current regression.

## 2026-06-19 BOLD-VERIFY PA/Node-Expansion Slice

Environment:
- Agent: `CrimsonRiver` / `cod-b`.
- Target dir: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Release extension rebuilt with `maturin develop --release --features pyo3/abi3-py310`.
- RCH note: `public_api_gauntlet` ran on `ovh-a`; `networkx_head_to_head`
  cut-metric rows require a remote worker with `numpy` in `.venv`. `hz1`/`hz2`
  failed before timing on `ModuleNotFoundError: numpy`, so local direct timing
  was used only for the rejected after-patch route and the source was reverted.

| Bead | Workload | FNX mean | NetworkX mean | FNX speedup | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-04z53.9156` | raw `preferential_attachment` repeated-overlap, current re-baseline | 378.79 ms | 586.12 ms | 1.55x | No-op; current row already winning/no source change |
| `br-r37-c1-21yfw` | `node_expansion`, BA2500/S1250 baseline | 773.11 us | 348.66 us | 0.45x | Loss confirmed |
| `br-r37-c1-21yfw` | `node_expansion`, WS2500/S625 baseline | 372.80 us | 190.48 us | 0.51x | Loss confirmed |
| `br-r37-c1-21yfw` | minimal raw-boundary guard, BA local direct after-patch | 466.56 us | 297.17 us | 0.64x | Rejected/reverted |
| `br-r37-c1-21yfw` | minimal raw-boundary guard, WS local direct after-patch | 213.18 us | 147.31 us | 0.69x | Rejected/reverted |

Score:
- Win/loss/neutral accounting: `1` current measured win/no-op, `1` attempted
  loss rejected, `0` shipped perf keeps.
- Conformance evidence: focused graph expansion/conformance route passed `10`
  tests while the patch was applied; source was reverted after the keep gate
  failed. Final post-revert focused graph/link-prediction route passed `14`
  tests, so no new conformance surface remains.
- Ledger hygiene: both the PA no-op and `node_expansion` rejection are recorded
  in `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **no new release claim**. PA is not a
current measured gap on the raw gauntlet row; `node_expansion` still needs a
single PyO3 validate+compute primitive or a worker-env-normalized Criterion row
before public dispatch can beat NetworkX.

## 2026-06-19 Cut-Metric Gauntlet Slice

Environment:
- Commit under verification before this scorecard: `c04404c9a`.
- Reference: upstream `networkx 3.6.1` from `.venv`.
- Subject: editable local `franken_networkx` with release `_fnx.abi3.so`
  rebuilt by `maturin develop --release`.
- Bench command: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b cargo bench -p fnx-python --bench networkx_head_to_head -- --sample-size 20 --warm-up-time 1 --measurement-time 2`.
- Criterion artifacts: `/data/projects/.rch-targets/franken_networkx-cod-b/criterion/networkx_head_to_head_cut_metrics/`.
- Focused conformance: `AGENT_NAME=CrimsonRiver .venv/bin/python -m pytest tests/python/test_graph_metrics_expansion.py tests/python/test_graph_metrics_conformance.py -q` passed with `197 passed in 0.85s`.
- Compile gate: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b cargo check -p fnx-python --benches` passed.

| Bead | Workload | FNX mean | NetworkX mean | FNX speedup | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-04z53.9155` | `edge_expansion`, BA2500 m=3, `|S|=1250` | 0.724 ms | 3.027 ms | 4.18x | Keep |
| `br-r37-c1-04z53.9155` | `edge_expansion`, WS2500 k=8 p=0.05, `|S|=625` | 0.367 ms | 1.775 ms | 4.84x | Keep |
| `br-r37-c1-04z53.9153` | `node_expansion`, BA2500 m=3, `|S|=1250` after revert | 1.080 ms | 0.481 ms | 0.445x | Rejected public fast path |
| `br-r37-c1-04z53.9153` | `node_expansion`, WS2500 k=8 p=0.05, `|S|=625` after revert | 0.488 ms | 0.281 ms | 0.577x | Rejected public fast path |

Pre-revert `node_expansion` evidence:
- BA2500/S1250 native public route: 0.713 ms vs NetworkX 0.527 ms, speedup 0.74x.
- WS2500/S625 native public route: 0.359 ms vs NetworkX 0.249 ms, speedup 0.69x.
- Revert rationale: the native public route improved over FNX fallback but did not beat
  the original NetworkX implementation, so it failed the campaign keep gate.

Score:
- Performance evidence: 32/40. One public fast path is a measured keep; one was measured
  and reverted instead of left pending.
- Conformance evidence: 25/25 for the focused cut-metric files. The run exposed and
  this commit fixes simple Graph/DiGraph `edge_boundary(S, T)` overlap ordering
  before recording the scorecard as green.
- Benchmark rigor: 16/20. Same interpreter, same graphs, setup outside timed loops,
  Criterion sample size 20; no flamegraph attribution in this narrow slice.
- Ledger hygiene: 20/20. Both keep and rejection are recorded in
  `docs/progress/perf-negative-results.md`.

Release readiness verdict for this slice: **conditional pass for `edge_expansion`;
no release claim for `node_expansion`**. Full project release readiness remains blocked
on the broader pending perf backlog and full conformance matrix.

## 2026-06-19 Sampled Edge-Betweenness Gauntlet Slice

Environment:
- Commit under verification: `2032eb47b`.
- Reference: upstream `networkx 3.6.1` from `.venv`.
- Subject: editable local `franken_networkx` with release `_fnx.abi3.so`
  rebuilt by `maturin develop --release`.
- Bench command: filtered Criterion `fnx-python` bench for
  `edge_betweenness_centrality(gnp_random_graph(600, 0.03, seed=1), k=50, seed=1)`.
- Criterion artifacts:
  `/data/projects/.rch-targets/franken_networkx-cod-a/criterion/networkx_head_to_head_edge_betweenness/`.
- Focused conformance: `test_betweenness_k_sampled_conformance_guard.py` passed
  with `19 passed in 0.44s`.
- Compile gate: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --benches` passed.

| Bead | Workload | FNX mean | NetworkX mean | FNX speedup | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-8ox3z.1` | `edge_betweenness_centrality`, gnp600 p=0.03, `k=50`, `seed=1` | 36.214 ms | 149.119 ms | 4.12x | Keep |

Score delta:
- Performance evidence: +4. The sibling edge sampled route now has a real
  Criterion head-to-head keep instead of a pending code-first note.
- Conformance evidence: +2. The no-delegation sampled betweenness guard remains
  green for node and edge variants.
- Ledger hygiene: +2. The pending `br-r37-c1-8ox3z.1` row is retired with a
  concrete retry condition and artifact path.

Release readiness verdict for this slice: **conditional pass for sampled
`edge_betweenness_centrality` on unweighted simple graphs**. Weighted, multigraph,
and unsupported parameter combinations still intentionally route through the
NetworkX parity path.

## 2026-06-19 Assortativity Raw/Public Gauntlet Slice

Environment:
- Commit under verification: `2032eb47b` plus working-tree revert for the
  rejected `node_degree_xy` raw source.
- Reference: upstream `networkx 3.6.1` from `.venv`.
- Subject: editable local `franken_networkx` with release `_fnx.abi3.so`
  rebuilt by `maturin develop --release`.
- Bench commands:
  - Public group: `cargo bench -p fnx-python --bench networkx_head_to_head -- networkx_head_to_head_assortativity --sample-size 20 --warm-up-time 1 --measurement-time 2`.
  - Raw group: `cargo bench -p fnx-python --bench networkx_head_to_head -- networkx_head_to_head_assortativity_raw --sample-size 20 --warm-up-time 1 --measurement-time 2`.
- Criterion artifacts:
  `/data/projects/.rch-targets/franken_networkx-cod-b/criterion/networkx_head_to_head_assortativity*/`.
- Focused conformance: `test_node_degree_xy_iter_order_parity.py`,
  `test_assortativity_scalars_parity.py`, and
  `test_assortativity_extensions_parity.py` passed with `234 passed in 1.57s`.
- Compile gate: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --benches` passed on `hz1`.
- Remote bench note: `rch exec -- cargo bench ... networkx_head_to_head_assortativity`
  built on `ovh-a` but failed at runtime because that worker lacks Python
  `networkx`; the timed Criterion runs therefore used the local `.venv`.

| Bead | Workload | FNX mean | NetworkX mean | Ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-04z53.9147` | raw `_fnx.degree_mixing_dict_rust`, h512/s32 | 0.568 ms | 112.368 ms | 197.68x | Keep |
| `br-r37-c1-04z53.9147` | public `fnx.degree_mixing_dict`, h512/s32 | 12.165 ms | 107.249 ms | 8.82x | Keep |
| `br-r37-c1-04z53.9149` | raw `_fnx.node_degree_xy_rust`, h512/s32 | 2.468 ms | 116.486 ms | 47.20x, invalid | Reject, reverted |
| `br-r37-c1-04z53.9149` | raw directed `_fnx.node_degree_xy_rust`, l512/f32 | 4.413 ms | 124.292 ms | 28.17x, invalid | Reject, reverted |
| `br-r37-c1-04z53.9149` | public `fnx.node_degree_xy`, h512/s32 | 579.651 ms | 113.781 ms | 0.196x | Follow-up needed |
| `br-r37-c1-04z53.9149` | public directed `fnx.node_degree_xy`, l512/f32 | 360.700 ms | 115.593 ms | 0.320x | Follow-up needed |
| `br-r37-c1-04z53.9152` | raw `_fnx.average_degree_connectivity`, h512/s32/i256 | 0.149 ms | 52.729 ms | 354.68x | Keep |
| `br-r37-c1-04z53.9152` | public `fnx.average_degree_connectivity`, h512/s32/i256 | 27.992 ms | 52.300 ms | 1.87x | Keep |

Revert rationale for `.9149`: the raw fast path emitted the wrong NetworkX
contract on the measured graph. Undirected raw emitted `16895` tuples vs
NetworkX `33790` and started `(33, 1)` vs `(1, 34)`; directed started
`(32, 1)` vs `(1, 32)`. The optimization was fast but not a valid substitute.

Score delta:
- Performance evidence: +6. Two assortativity rows moved from pending to real
  keeps, and one row moved to a measured rejection with a source revert.
- Conformance evidence: +3. Public assortativity conformance stayed green after
  the raw rejection/revert.
- Ledger hygiene: +3. Raw and public wins/losses are all recorded with ratios
  and retry guidance.

Release readiness verdict for this slice: **conditional pass for
`degree_mixing_dict` and `average_degree_connectivity`; no release claim for
`node_degree_xy` acceleration**.

## 2026-06-19 Community Link-Prediction Gauntlet Slice

Environment:
- Commit under verification: `dc9b8d5b`.
- Reference: upstream `networkx 3.6.1` from `.venv`.
- Subject: editable local `franken_networkx`; the measured WIC route is
  Python-level and used the existing local release `_fnx.abi3.so`.
- Bench command: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONPATH=/data/projects/franken_networkx/crates/fnx-python/benches:/data/projects/franken_networkx/python:/data/projects/franken_networkx/.venv/lib/python3.13/site-packages taskset -c 2 cargo bench -p fnx-python --bench public_api_gauntlet -- within_inter_cluster --sample-size 10 --warm-up-time 1 --measurement-time 4`.
- Criterion artifacts:
  `/data/projects/.rch-targets/franken_networkx-cod-a/criterion/within_inter_cluster_explicit_community/`.
- Workload: 480-node community-labeled sparse block graph, 6000 explicit
  candidate non-edges, 100 API calls/sample.
- Focused conformance: `tests/python/test_community_link_prediction_parity.py`
  passed with `217 passed in 0.64s`.
- Compile gate: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --benches` passed on `hz2`.

| Bead | Workload | FNX mean | NetworkX mean | Ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-04z53.9141` | public `within_inter_cluster`, explicit 6000-pair community ebunch | 340.828 ms | 570.661 ms | 1.67x | Keep |

Noise gate:
- A preliminary 25-call Criterion row was also positive (`94.609 ms` vs
  `162.547 ms`, `1.72x`) but failed the CV threshold (`7.44%`/`8.60%`), so the
  keep decision uses the 100-call row above (`0.99%`/`2.39%` CV).

Score delta:
- Performance evidence: +4. The public WIC cached-adjacency row moved from
  code-first pending to a measured head-to-head keep.
- Conformance evidence: +2. The community link-prediction parity guard remains
  green across default, explicit, delta, laziness, and error cases.
- Benchmark rigor: +2. The final row is pinned to one CPU, reports CV below the
  5% gate, and records the discarded noisy row.
- Ledger hygiene: +2. The pending WIC ledger row is retired with a concrete
  retry condition and artifact path.

Release readiness verdict for this slice: **conditional pass for public
`within_inter_cluster` on simple community-labeled graphs with explicit ebunches**.
Default-ebunch and tiny-ebunch behavior remain separate workload gates.

## 2026-06-19 Undirected Non-Edges Gauntlet Slice

Environment:
- Commit under verification before revert: `f233ece94` plus the code-first
  native undirected `non_edges` route already present in the worktree.
- Reference: vendored original NetworkX `3.7rc0.dev0` from
  `legacy_networkx_code/networkx/networkx`.
- Bench command: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONPATH=/data/projects/franken_networkx/crates/fnx-python/benches:/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code/networkx taskset -c 2 cargo bench -p fnx-python --bench public_api_gauntlet -- non_edges_sparse_undirected --sample-size 10 --warm-up-time 1 --measurement-time 4`.
- Criterion artifacts:
  `/data/projects/.rch-targets/franken_networkx-cod-a/criterion/non_edges_sparse_undirected/`.
- Workload: 900-node sparse undirected graph, `p=0.008`, deterministic
  seed `9143`, 401,391 generated non-edges, 4 API calls/sample, setup outside
  the timed call, order-sensitive checksum parity at helper import.
- Focused conformance after revert: `test_non_edges_order_conformance_guard.py`
  plus targeted graph-utility non-edges guards passed with `47 passed in 1.01s`.
- Compile gate: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --benches` passed on `hz2`.

| Bead | Workload | FNX mean | NetworkX mean | Ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-04z53.9143` | public `non_edges`, sparse undirected default ebunch | 458.750 ms | 470.775 ms | 1.026x | Reject, reverted |

Revert rationale: the native row-dispatch route was technically faster by
`2.55%`, but the mean confidence intervals overlapped (`452.665..465.576 ms`
vs `464.013..478.087 ms`) and the gain was below the gauntlet keep threshold.
The public source path was reverted to the generic `set(graph)` / `graph[u]`
loop, and the dedicated guard now preserves parity plus no NetworkX delegation
without locking in the reverted `__getitem__` bypass.

Score delta:
- Performance evidence: +2. The pending `non_edges` route moved to measured
  neutral evidence instead of a code-first claim.
- Conformance evidence: +1. Exact order and public fallback guards stayed green
  after the revert.
- Ledger hygiene: +2. The negative-evidence ledger now blocks repeating this
  Python-level native-row route without a materially different generator design.

Release readiness verdict for this slice: **no release claim for undirected
`non_edges` acceleration**. The next credible route is a batched Rust/PyO3
non-edge generator measured against this same Criterion row.

## 2026-06-19 CCPA Link-Prediction Gauntlet Slice

Environment:
- Commit under verification: working tree with the existing
  `br-r37-c1-04z53.9140` raw CCPA scoring lever.
- Reference: vendored original NetworkX from `legacy_networkx_code/networkx`,
  asserted by the Criterion setup before timing.
- Subject: editable local `franken_networkx` with release `_fnx.abi3.so`
  rebuilt by `maturin develop --release -m crates/fnx-python/Cargo.toml
  --features pyo3/abi3-py310`.
- Bench command: `AGENT_NAME=CrimsonRiver PYTHONHASHSEED=0 OMP_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b taskset -c 2 cargo bench -p fnx-python --bench networkx_head_to_head -- networkx_head_to_head_link_prediction --sample-size 10 --warm-up-time 3 --measurement-time 15`.
- Criterion artifacts:
  `/data/projects/.rch-targets/franken_networkx-cod-b/criterion/networkx_head_to_head_link_prediction/`.
- Workload: public `common_neighbor_centrality`, 600-node sparse undirected
  graph, `p=0.03`, 2000 deterministic explicit non-edge pairs, `alpha=0.8`,
  setup outside the timed calls.
- Focused conformance: `tests/python/test_link_prediction_conformance.py`
  and `tests/python/test_link_prediction_edge_case_conformance_guard.py`
  passed with `397 passed in 1.05s`.
- Compile gate: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --benches`
  passed on `hz1`.

| Bead | Workload | FNX mean | NetworkX mean | Ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-04z53.9140` | public `common_neighbor_centrality`, explicit 2000-pair ebunch | 38.862787 ms | 143.846328 ms | 3.701x | Keep |

Noise gate:
- A shorter local row was positive (`37.418 ms` vs `163.987 ms`, `4.383x`)
  but noisy (`6.358%`/`10.509%` CV), and a first pinned row was still above
  the FNX CV gate (`5.844%`). The keep decision uses the final pinned row
  (`1.895%`/`1.316%` CV).

Score delta:
- Performance evidence: +4. The CCPA raw scoring lever moved from code-first
  pending to a measured public head-to-head keep.
- Conformance evidence: +2. Focused link-prediction parity and edge-case guards
  stayed green against the rebuilt extension.
- Benchmark rigor: +2. The final row is pinned to one CPU, reports sub-2% CVs,
  asserts the vendored NetworkX oracle, and records the discarded noisy rows.
- Ledger hygiene: +2. The pending CCPA ledger row is retired with artifact path,
  ratio, and a specific next-route condition.

Release readiness verdict for this slice: **conditional pass for public
`common_neighbor_centrality` on simple undirected graphs with explicit ebunches**.
Default-ebunch and all-pairs/source-block reuse remain separate workload gates.

## 2026-06-19 Raw AA/RA Link-Prediction Gauntlet Slice

Environment:
- Commit under verification: `ad5dba875` plus this harness-only working tree.
- Reference: vendored original NetworkX `3.7rc0.dev0` from
  `legacy_networkx_code/networkx/networkx`.
- Subject: editable local `franken_networkx`; release extension rebuilt with
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- .venv/bin/maturin develop --release --features pyo3/abi3-py310`.
- Bench command: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONPATH=/data/projects/franken_networkx/crates/fnx-python/benches:/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code/networkx taskset -c 2 cargo bench -p fnx-python --bench public_api_gauntlet -- raw_ --sample-size 10 --warm-up-time 1 --measurement-time 8`.
- Criterion artifacts:
  `/data/projects/.rch-targets/franken_networkx-cod-a/criterion/raw_adamic_adar_repeated_overlap/`
  and `/data/projects/.rch-targets/franken_networkx-cod-a/criterion/raw_resource_allocation_repeated_overlap/`.
- Workload: 800-node clustered sparse graph, 2,414 edges, 1,600
  high-common-neighbor candidate pairs repeated to 6,400 explicit ebunch
  entries, 80 raw API calls/sample, setup outside the timed call. Helper import
  asserts FNX/NetworkX checksum parity for both scorers.
- Focused conformance: `test_link_prediction_edge_case_conformance_guard.py`
  and `test_link_prediction_no_conversion_parity.py` passed with
  `153 passed in 2.05s`.
- Compile gate: `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --benches` passed on `hz1`.

| Bead | Workload | FNX mean | NetworkX mean | Ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `br-r37-c1-04z53.9148` | raw `_fnx.adamic_adar_index`, repeated-overlap explicit ebunch | 337.308 ms | 1581.235 ms | 4.69x | Keep |
| `br-r37-c1-04z53.9148` | raw `_fnx.resource_allocation_index`, repeated-overlap explicit ebunch | 338.691 ms | 1523.139 ms | 4.50x | Keep |

Noise gate:
- The first 40-call pass was positive (`5.36x` AA, `4.10x` RA) but had
  CV above the 5% keep gate on several rows. The final 80-call row above is the
  keep evidence: CVs are `1.42%`, `1.02%`, `0.78%`, and `2.70%`.

Score delta:
- Performance evidence: +4. The AA/RA common-neighbor weight memo moved from
  code-first pending to measured head-to-head keeps.
- Conformance evidence: +2. Public Python link-prediction parity and repeated
  edge-case guards remain green after the release rebuild.
- Benchmark rigor: +2. The noisy first row is recorded and discarded; the final
  row uses pinned CPU, same graph/ebunch, same process, vendored NetworkX, and
  all CVs under 5%.
- Ledger hygiene: +2. The negative-evidence ledger now records the keep and the
  activation-threshold retry condition for tiny ebunches.

Release readiness verdict for this slice: **conditional pass for raw AA/RA
repeated-overlap explicit-ebunch scoring**. Public wrapper routing and tiny
ebunch activation thresholds remain separate workload gates.
