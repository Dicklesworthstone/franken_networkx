# Gauntlet Release-Readiness Scorecard

Scope: code-first perf backlog verification for `br-r37-c1-04z53` plus
`br-r37-c1-tbh4q`.

Current verdict: not release-ready for the full campaign. Sixteen backlog rows
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
| 2026-06-19 | `br-r37-c1-04z53.9146` | public `common_neighbor_centrality` shared-source explicit ebunch, `left_only=512`, `right_only=512`, `common=256`, `repeats=2048`, `alpha=0.8` | fnx mean `99.802124 ms`, CV `1.03%` | vendored NetworkX mean `260.973500 ms`, CV `0.75%` | `2.61x` | Pass | focused link-prediction conformance: `421 passed`; max abs diff `0.0` | Keep |
| 2026-06-19 | `br-r37-c1-04z53.9145/.9150/.9151` | raw repeated explicit-ebunch link prediction, `4096` repeated `("u", "v")` pairs on `left_only=512`, `right_only=512`, `common=256` | Jaccard `2.352256 ms`; Adamic-Adar `2.334660 ms`; resource allocation `2.352473 ms` | NetworkX `189.237499 ms`; `365.904875 ms`; `323.792890 ms` | Jaccard `80.45x`; AA `156.73x`; RA `137.64x` | Pass | focused link-prediction conformance: `421 passed`; checksum parity | Keep, combined evidence |
| 2026-06-19 | `br-r37-c1-04z53.9140` | public `common_neighbor_centrality` on a 600-node sparse undirected graph with 2000 explicit non-edge pairs | fnx mean `38.862787 ms`, CV `1.895%` | vendored NetworkX mean `143.846328 ms`, CV `1.316%` | `3.701x` | Pass | focused link-prediction conformance: `397 passed` | Keep |
| 2026-06-19 | `br-r37-c1-zid1b` | MultiDiGraph SCC and descendants on an 1800-node block/parallel-arc MultiDiGraph | SCC `925.39 us`; descendants `579.76 us` | SCC `2.2594 ms`; descendants `1.0212 ms` | SCC `2.44x`; descendants `1.76x`; full-surface probe `9` wins / `1` neutral / `0` losses | Pass | focused MultiDiGraph connectivity/traversal guards: `391 + 187 + 2 passed` | Keep |
| 2026-06-19 | `br-r37-c1-p55u8` | `franken_networkx.convert_matrix` module-path builders/exporters on dense/sparse adjacency and graph export fixtures | builders: `from_numpy_array` `3.220225 ms`, `from_scipy_sparse_array` `3.248513 ms`; exporters: `to_numpy_array` `36.362134 ms`, `to_scipy_sparse_array` `1.938103 ms` | NetworkX builders: `1.962289 ms`, `1.102917 ms`; exporters: `35.872536 ms`, `2.834654 ms` | builders lose `0.609x` / `0.340x`; exporters neutral/win `0.987x` / `1.463x` noisy | Fail as a perf keep; checksums match | module-route + conversion guards: `32 passed` | Reject; route is correctness/type-surface only |
| 2026-06-19 | `br-r37-c1-8ox3z` | public `betweenness_centrality(G, k=50, seed=1)` on `gnp_random_graph(600, 0.03, seed=1)` | fnx mean `3.260962 ms`, CV `1.53%` | vendored NetworkX mean `77.422671 ms`, CV `0.35%` | `23.74x` | Pass | sampled betweenness no-delegation guard: `19 passed`; max abs diff `4.34e-19` | Keep |
| 2026-06-19 | `br-r37-c1-04z53.9139` | raw `cn_soundarajan_hopcroft` and `ra_index_soundarajan_hopcroft` on the 800-node repeated-overlap explicit ebunch public-gauntlet fixture | CN-SH FNX mean `413.047 ms`; RA-SH FNX mean `468.675 ms` | CN-SH NetworkX mean `1535.405 ms`; RA-SH NetworkX mean `2077.587 ms` | CN-SH `3.72x`; RA-SH `4.43x` | Pass: disjoint Criterion CIs; direct-loop checksums matched | focused community/link-prediction conformance: `634 passed` | Keep |
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
- CCPA shared-source command:
  `AGENT_NAME=CrimsonRiver PYTHONHASHSEED=0 OMP_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/.scratch/franken_networkx-cod-a-8ox3z-20260619T175850Z/python:/data/projects/.scratch/franken_networkx-cod-a-8ox3z-20260619T175850Z/legacy_networkx_code/networkx CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a taskset -c 4 /data/projects/franken_networkx/.venv/bin/python` using identical FNX/NetworkX public `common_neighbor_centrality` inputs with `left_only=512`, `right_only=512`, `common=256`, `repeats=2048`, `target_count=64`, and `alpha=0.8`.
- Repeated-pair raw link-prediction command:
  `AGENT_NAME=CrimsonRiver PYTHONHASHSEED=0 OMP_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/.scratch/franken_networkx-cod-a-8ox3z-20260619T175850Z/python:/data/projects/.scratch/franken_networkx-cod-a-8ox3z-20260619T175850Z/legacy_networkx_code/networkx CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a taskset -c 4 /data/projects/franken_networkx/.venv/bin/python` using raw `_fnx.jaccard_coefficient`, `_fnx.adamic_adar_index`, and `_fnx.resource_allocation_index` against vendored NetworkX on identical `4096` repeated explicit pairs. This row validates the combined endpoint-cache/slab/pair-memo path; it is not isolated per-lever attribution.
- Sampled node betweenness command:
  `AGENT_NAME=CrimsonRiver PYTHONHASHSEED=0 OMP_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/.scratch/franken_networkx-cod-a-8ox3z-20260619T175850Z/python:/data/projects/.scratch/franken_networkx-cod-a-8ox3z-20260619T175850Z/legacy_networkx_code/networkx CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a taskset -c 4 /data/projects/franken_networkx/.venv/bin/python` using identical FNX/NetworkX `gnp_random_graph(600, 0.03, seed=1)` inputs, `k=50`, `seed=1`, and 10 timed calls per engine.
- MultiDiGraph connectivity command:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b cargo bench -p fnx-python --bench networkx_head_to_head -- multidigraph_connectivity --sample-size 20 --warm-up-time 1 --measurement-time 3` on `vmi1227854`, plus the focused guards listed above. The broad `test_dicsr_cache_parity.py` failure noted in the ledger is unrelated pre-existing directed finalize-order debt.
- `convert_matrix` command:
  `AGENT_NAME=CrimsonRiver PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/.scratch/franken_networkx-cod-a-p55u8-20260619T181636Z/python:/data/projects/.scratch/franken_networkx-cod-a-p55u8-20260619T181636Z/legacy_networkx_code/networkx CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a taskset -c 4 /data/projects/franken_networkx/.venv/bin/python` using direct module-path calls against vendored NetworkX. A default-node list-materialization patch was also tested and reverted because `from_numpy_array` / `from_scipy_sparse_array` remained losing (`0.587x` / `0.363x`).
- Soundarajan-Hopcroft benchmark command:
  `AGENT_NAME=CrimsonRiver PYTHONHASHSEED=0 OMP_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/.scratch/franken_networkx-cod-a-20260619T053601Z/crates/fnx-python/benches:/data/projects/.scratch/franken_networkx-cod-a-20260619T053601Z/python:/data/projects/.scratch/franken_networkx-cod-a-20260619T053601Z/legacy_networkx_code/networkx CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a taskset -c 4 cargo bench -p fnx-python --bench public_api_gauntlet -- 'raw_.*soundarajan' --sample-size 10 --warm-up-time 1 --measurement-time 8`
  RCH note: `rch exec -- cargo bench -p fnx-python --bench public_api_gauntlet -- 'raw_.*soundarajan' ...` built successfully on `hz1` but failed before measurement with `ModuleNotFoundError("No module named 'public_api_gauntlet'")`; the local Criterion run above is the keep gate.
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
  Soundarajan-Hopcroft estimates:
  `/data/projects/.rch-targets/franken_networkx-cod-a/criterion/raw_*soundarajan_hopcroft_repeated_overlap/`.
- Host context: 64 logical CPUs; load average during the pinned run was
  `27.43, 43.55, 29.56`.
- Python oracle identity: `legacy_networkx_code/networkx/networkx/__init__.py`,
  NetworkX `3.7rc0.dev0`.

## Score

| Pillar | Score | Notes |
| --- | ---: | --- |
| Performance evidence | 13 keeps / 16 measured rows | Edge expansion, MultiDiGraph SCC/descendants, weighted flow hierarchy, degree mixing, average degree connectivity, generic CCPA, shared-source CCPA, sampled node betweenness, repeated-pair raw link prediction (`.9145/.9150/.9151`), raw Soundarajan-Hopcroft, and attr-heavy `to_undirected` beat NetworkX; node expansion, node_degree_xy, and `convert_matrix` graph-builder routing lost or drifted and were reverted/no-shipped as perf keeps. Win/loss/neutral: `13/3/0`. |
| Conformance evidence | focused guards green for kept rows and rejects | Edge expansion reports `197 passed`; MultiDiGraph reports `391 + 187 + 2 passed`; flow hierarchy reports `99 passed`; assortativity reports `234 passed`; CCPA reports `397 passed`; shared-source/repeated-pair link prediction reports `421 passed`; sampled betweenness reports `19 passed`; Soundarajan-Hopcroft reports `634 passed`; `to_undirected` reports `133 + 245 passed`; `convert_matrix` reports `32 passed`. |
| Negative-evidence discipline | 16 / 16 updated | The ledger records keep, reject, noisy, contaminated, remote-runtime, post-analysis-crash, direct-loop, combined-evidence, and invalid-output measurement attempts. |
| Backlog conversion | 16 measured rows represented here; pending rows remain | Campaign remains red until the rest of the pending code-first rows are measured or reverted. |

Next required rows: the remaining link-prediction `.9144..9151` cluster and
the rest of the June pending rows in `docs/progress/perf-negative-results.md`.
