# Gauntlet Release-Readiness Scorecard

Scope: code-first perf backlog verification for `br-r37-c1-04z53` plus
`br-r37-c1-tbh4q`.

Current verdict: not release-ready for the full campaign. Eight backlog beads
are represented here with measured head-to-head evidence; the remaining pending
rows still need the same treatment.

## Measured Rows

| Date | Bead | Workload | Subject | Oracle | Ratio vs NetworkX | CV gate | Conformance | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-06-19 | `br-r37-c1-04z53.9155` | `edge_expansion(G, S, T=None)` on BA2500/S1250 and WS2500/S625 simple-undirected cuts | fnx means `0.724 ms` BA, `0.367 ms` WS | NetworkX means `3.027 ms` BA, `1.775 ms` WS | `4.18x` BA speedup, `4.84x` WS speedup | Pass in `networkx_head_to_head` run | focused cut conformance: `197 passed` | Keep |
| 2026-06-19 | `br-r37-c1-04z53.9153` | `node_expansion(G, S)` on BA2500/S1250 and WS2500/S625 simple-undirected cuts | native public route means `0.713 ms` BA, `0.359 ms` WS | NetworkX means `0.527 ms` BA, `0.249 ms` WS | `0.74x` BA, `0.69x` WS | Fail as a keep | public fast path reverted | Reject |
| 2026-06-19 | `br-r37-c1-04z53.9154` | `flow_hierarchy(G, weight="weight")` on a 900-node weighted cyclic DAG, 100 public API calls per Criterion sample | fnx mean `7.9309 ms/call`, median `7.8704 ms/call`, CV `2.80%` | vendored NetworkX `3.7rc0.dev0` mean `13.1834 ms/call`, median `13.1256 ms/call`, CV `2.12%` | `1.662x` mean speedup, `1.668x` median speedup | Pass | `tests/python/test_network_summary_measures_conformance.py -q`: `99 passed` | Keep |
| 2026-06-19 | `br-r37-c1-04z53.9147` | raw/public `degree_mixing_dict` on hub-spoke h512/s32 | raw `_fnx` mean `0.568 ms`; public fnx mean `12.165 ms` | NetworkX means `112.368 ms` raw-group, `107.249 ms` public-group | raw `197.68x`; public `8.82x` | Pass | focused assortativity conformance: `234 passed` | Keep |
| 2026-06-19 | `br-r37-c1-04z53.9149` | raw/public `node_degree_xy` on hub-spoke h512/s32 and directed fan l512/f32 | raw means `2.468 ms` undirected, `4.413 ms` directed; public means `579.651 ms`, `360.700 ms` | NetworkX means `116.486 ms`, `124.292 ms`, `113.781 ms`, `115.593 ms` | raw `47.20x`/`28.17x` but invalid; public `0.196x`/`0.320x` | Fail: raw output drift and public loss | focused public conformance stayed green; raw source reverted | Reject |
| 2026-06-19 | `br-r37-c1-04z53.9152` | raw/public `average_degree_connectivity` on hub-spoke/isolate h512/s32/i256 | raw `_fnx` mean `0.149 ms`; public fnx mean `27.992 ms` | NetworkX means `52.729 ms` raw-group, `52.300 ms` public-group | raw `354.68x`; public `1.87x` | Pass | focused assortativity conformance: `234 passed` | Keep |
| 2026-06-19 | `br-r37-c1-04z53.9140` | public `common_neighbor_centrality` on a 600-node sparse undirected graph with 2000 explicit non-edge pairs | fnx mean `38.862787 ms`, CV `1.895%` | vendored NetworkX mean `143.846328 ms`, CV `1.316%` | `3.701x` | Pass | focused link-prediction conformance: `397 passed` | Keep |
| 2026-06-19 | `br-r37-c1-tbh4q` | `DiGraph.to_undirected()` attr-heavy 3000-node/12000-edge directed graph, 100 calls/sample, direct pinned loop | fnx mean `31.144 ms/call`, CV `3.551%` | vendored NetworkX `3.7rc0.dev0` mean `38.003 ms/call`, CV `2.403%` | `1.220x` | Pass | focused to-undirected/reverse guards: `133 passed`; copy/lazy stress: `245 passed` | Keep |

## Method

- Flow hierarchy commit measured: `c04404c9a9117acad112fbfd5c96b1f6f6e850c0`.
- Flow hierarchy benchmark command:
  `PYTHONHASHSEED=0 OMP_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/.scratch/franken_networkx-cod-a-gauntlet-verify-20260619/crates/fnx-python/benches:/data/projects/.scratch/franken_networkx-cod-a-gauntlet-verify-20260619/python:/data/projects/.scratch/franken_networkx-cod-a-gauntlet-verify-20260619/legacy_networkx_code/networkx CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a taskset -c 2 cargo bench -p fnx-python --bench public_api_gauntlet -- --sample-size 10 --warm-up-time 1 --measurement-time 15`
- Cut-metric benchmark command:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b cargo bench -p fnx-python --bench networkx_head_to_head -- --sample-size 20 --warm-up-time 1 --measurement-time 2`
- Assortativity benchmark commands:
  `PYTHONHASHSEED=0 OMP_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b cargo bench -p fnx-python --bench networkx_head_to_head -- networkx_head_to_head_assortativity --sample-size 20 --warm-up-time 1 --measurement-time 2`
  and the same command filtered to `networkx_head_to_head_assortativity_raw`.
- CCPA benchmark command:
  `AGENT_NAME=CrimsonRiver PYTHONHASHSEED=0 OMP_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b taskset -c 2 cargo bench -p fnx-python --bench networkx_head_to_head -- networkx_head_to_head_link_prediction --sample-size 10 --warm-up-time 3 --measurement-time 15`
- `to_undirected` benchmark command:
  `AGENT_NAME=CrimsonRiver PYTHONHASHSEED=0 OMP_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/franken_networkx/crates/fnx-python/benches:/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code/networkx taskset -c 4 .venv/bin/python` using the `digraph_to_undirected_attr_heavy` helper from `crates/fnx-python/benches/public_api_gauntlet.py`.
- `to_undirected` diagnostic Criterion artifacts:
  `/data/projects/.rch-targets/franken_networkx-cod-a/criterion/digraph_to_undirected_attr_heavy/`.
  These were positive but not the keep gate because FNX CV exceeded 5% in shorter Criterion rows and the 100-repeat Criterion run emitted SIGSEGV after writing estimates.
- Criterion estimates:
  `/data/projects/.rch-targets/franken_networkx-cod-a/criterion/flow_hierarchy_weighted_cyclic_dag/{fnx,networkx}/new/estimates.json`.
  Assortativity estimates:
  `/data/projects/.rch-targets/franken_networkx-cod-b/criterion/networkx_head_to_head_assortativity*/`.
  CCPA estimates:
  `/data/projects/.rch-targets/franken_networkx-cod-b/criterion/networkx_head_to_head_link_prediction/`.
- Host context: 64 logical CPUs; load average during the pinned run was
  `27.43, 43.55, 29.56`.
- Python oracle identity: `legacy_networkx_code/networkx/networkx/__init__.py`,
  NetworkX `3.7rc0.dev0`.

## Score

| Pillar | Score | Notes |
| --- | ---: | --- |
| Performance evidence | 6 keeps / 8 measured rows | Edge expansion, weighted flow hierarchy, degree mixing, average degree connectivity, CCPA, and attr-heavy `to_undirected` beat NetworkX; node expansion and node_degree_xy lost or drifted and were reverted. |
| Conformance evidence | focused guards green for kept rows | Edge expansion reports `197 passed`; flow hierarchy reports `99 passed`; assortativity reports `234 passed`; CCPA reports `397 passed`; `to_undirected` reports `133 + 245 passed`. |
| Negative-evidence discipline | 8 / 8 updated | The ledger records keep, reject, noisy, contaminated, post-analysis-crash, and invalid-output measurement attempts. |
| Backlog conversion | 8 measured rows represented here; pending rows remain | Campaign remains red until the rest of the pending code-first rows are measured or reverted. |

Next required rows: the remaining link-prediction `.9139..9151` cluster and
the rest of the June pending rows in `docs/progress/perf-negative-results.md`.
