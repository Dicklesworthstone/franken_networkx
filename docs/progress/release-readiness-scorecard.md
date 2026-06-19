# Release Readiness Scorecard

Target: FrankenNetworkX no-gaps performance gauntlet.

Scope of this update: cut-metric public wrappers from the recent code-first
pending backlog (`br-r37-c1-04z53.9155` and `br-r37-c1-04z53.9153`) plus
sampled edge-betweenness verification (`br-r37-c1-8ox3z.1`) and raw
assortativity verification (`br-r37-c1-04z53.9147`, `.9149`, `.9152`) plus
community link-prediction verification (`br-r37-c1-04z53.9141`) and
undirected `non_edges` default-ebunch verification (`br-r37-c1-04z53.9143`)
plus CCPA link-prediction verification (`br-r37-c1-04z53.9140`).

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
